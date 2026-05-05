#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::fs::{self, File};
use std::io::{self, BufRead, BufReader, Read, Write};
use std::net::{TcpListener, TcpStream};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::thread;
use std::time::{Duration, Instant};

#[cfg(windows)]
use std::os::windows::process::CommandExt;

use tauri::path::BaseDirectory;
use tauri::webview::{DownloadEvent, WebviewWindowBuilder};
use tauri::{Manager, Url, WebviewUrl};
use zip::ZipArchive;

const APP_NAME: &str = "PDF文件翻译工具";
const RUNTIME_VERSION: &str = "2.5.10";

#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x08000000;

#[derive(Default)]
struct BackendState {
    child: Mutex<Option<Child>>,
}

fn main() {
    tauri::Builder::default()
        .manage(BackendState::default())
        .setup(|app| {
            // 手动创建主窗口，挂载 on_download 处理器；否则 WebView2 默认不
            // 保存 Gradio 的下载链接，所有“下载”按钮看起来都没反应。
            let window =
                WebviewWindowBuilder::new(app, "main", WebviewUrl::App("index.html".into()))
                    .title("PDF文件翻译工具")
                    .inner_size(1200.0, 800.0)
                    .min_inner_size(900.0, 650.0)
                    .on_download(move |_window, event| match event {
                        DownloadEvent::Requested { url, destination } => {
                            let suggested_name = destination
                                .file_name()
                                .and_then(|n| n.to_str())
                                .map(|s| s.to_string())
                                .unwrap_or_else(|| {
                                    url.path_segments()
                                        .and_then(|mut segs| segs.next_back())
                                        .map(|s| s.to_string())
                                        .filter(|s| !s.is_empty())
                                        .unwrap_or_else(|| "download".to_string())
                                });
                            let default_dir = documents_home().join(APP_NAME).join("downloads");
                            let _ = fs::create_dir_all(&default_dir);
                            let mut dialog = rfd::FileDialog::new()
                                .set_title("保存翻译文件")
                                .set_directory(&default_dir)
                                .set_file_name(&suggested_name);
                            if let Some(ext) = Path::new(&suggested_name)
                                .extension()
                                .and_then(|s| s.to_str())
                            {
                                dialog = dialog
                                    .add_filter(format!("{} 文件", ext.to_uppercase()), &[ext]);
                            }
                            dialog = dialog.add_filter("所有文件", &["*"]);
                            match dialog.save_file() {
                                Some(path) => {
                                    *destination = path;
                                    true
                                }
                                None => false,
                            }
                        }
                        DownloadEvent::Finished { path, success, .. } => {
                            if success {
                                if let Some(path) = path {
                                    eprintln!("download saved: {}", path.display());
                                }
                            } else {
                                eprintln!("download cancelled or failed");
                            }
                            true
                        }
                        _ => true,
                    })
                    .build()?;
            let _ = window;

            let handle = app.handle().clone();
            thread::spawn(move || {
                if let Err(error) = start_backend(handle.clone()) {
                    set_status(&handle, &format!("启动失败：{error}"));
                    eprintln!("Failed to start backend: {error}");
                }
            });
            Ok(())
        })
        .on_window_event(|window, event| {
            if matches!(event, tauri::WindowEvent::CloseRequested { .. }) {
                stop_backend(&window.app_handle());
            }
        })
        .run(tauri::generate_context!())
        .expect("failed to run app");
}

fn start_backend(app: tauri::AppHandle) -> Result<(), String> {
    set_status(&app, "正在准备本地运行环境...");
    let runtime_dir = ensure_runtime(&app)?;
    let python_exe = runtime_dir.join("python.exe");
    let pythonw_exe = runtime_dir.join("pythonw.exe");
    let backend_python_exe = if pythonw_exe.exists() {
        pythonw_exe
    } else {
        python_exe.clone()
    };
    let startup_script = runtime_dir.join("start_pdf2zh.py");
    if !backend_python_exe.exists() || !startup_script.exists() {
        return Err(format!("运行环境不完整：{}", runtime_dir.display()));
    }

    let port = find_available_port(7860, 7900)?;
    let desktop_home = documents_home().join(APP_NAME);
    let config_home = desktop_home.join("config");
    fs::create_dir_all(&config_home).map_err(|error| error.to_string())?;
    fs::create_dir_all(desktop_home.join("output")).map_err(|error| error.to_string())?;
    fs::create_dir_all(desktop_home.join("tmp")).map_err(|error| error.to_string())?;

    set_status(&app, "正在启动翻译服务...");
    let mut command = Command::new(&backend_python_exe);
    command
        .arg(&startup_script)
        .current_dir(&runtime_dir)
        .env("PYTHONUNBUFFERED", "1")
        .env("GRADIO_SERVER_PORT", port.to_string())
        .env("PDF2ZH_DESKTOP_HOME", &desktop_home)
        .env("PDF2ZH_CONFIG_DIR", &config_home)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());

    #[cfg(windows)]
    command.creation_flags(CREATE_NO_WINDOW);

    let mut child = command
        .spawn()
        .map_err(|error| format!("无法启动 Python 后端：{error}"))?;

    if let Some(stdout) = child.stdout.take() {
        pipe_output("python stdout", stdout);
    }
    if let Some(stderr) = child.stderr.take() {
        pipe_output("python stderr", stderr);
    }

    let state = app.state::<BackendState>();
    *state.child.lock().map_err(|error| error.to_string())? = Some(child);

    set_status(&app, "正在等待本地服务就绪...");
    if !wait_for_server(port, Duration::from_secs(180)) {
        return Err("本地服务启动超时".to_string());
    }

    set_status(&app, "正在进入应用...");
    let url = Url::parse(&format!("http://127.0.0.1:{port}")).map_err(|error| error.to_string())?;
    let window = app
        .get_webview_window("main")
        .ok_or_else(|| "找不到主窗口".to_string())?;
    window.navigate(url).map_err(|error| error.to_string())?;
    Ok(())
}

fn ensure_runtime(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    let runtime_dir = local_data_home()
        .join(APP_NAME)
        .join(format!("python-runtime-{RUNTIME_VERSION}"));
    let marker = runtime_dir.join(".runtime-ready");
    if marker.exists()
        && runtime_dir.join("python.exe").exists()
        && runtime_dir.join("start_pdf2zh.py").exists()
    {
        return Ok(runtime_dir);
    }

    if runtime_dir.exists() {
        fs::remove_dir_all(&runtime_dir).map_err(|error| error.to_string())?;
    }
    fs::create_dir_all(&runtime_dir).map_err(|error| error.to_string())?;

    let zip_path = find_runtime_zip(app)?;
    set_status(app, "首次启动正在解压本地运行环境...");
    extract_zip(&zip_path, &runtime_dir, app)?;
    fs::write(marker, RUNTIME_VERSION).map_err(|error| error.to_string())?;
    Ok(runtime_dir)
}

fn find_runtime_zip(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    let mut candidates = Vec::new();
    for resource_name in ["python_portable.zip", "resources/python_portable.zip"] {
        if let Ok(path) = app.path().resolve(resource_name, BaseDirectory::Resource) {
            candidates.push(path);
        }
    }
    if let Ok(exe_path) = std::env::current_exe() {
        if let Some(exe_dir) = exe_path.parent() {
            candidates.push(exe_dir.join("python_portable.zip"));
            candidates.push(exe_dir.join("resources").join("python_portable.zip"));
        }
    }
    candidates.push(PathBuf::from("resources").join("python_portable.zip"));
    candidates.push(
        PathBuf::from("src-tauri")
            .join("resources")
            .join("python_portable.zip"),
    );

    candidates
        .into_iter()
        .find(|path| path.exists())
        .ok_or_else(|| "找不到 python_portable.zip".to_string())
}

fn extract_zip(zip_path: &Path, target_dir: &Path, app: &tauri::AppHandle) -> Result<(), String> {
    let file = File::open(zip_path).map_err(|error| error.to_string())?;
    let mut archive = ZipArchive::new(file).map_err(|error| error.to_string())?;
    let total = archive.len();
    for index in 0..total {
        let mut entry = archive.by_index(index).map_err(|error| error.to_string())?;
        let Some(relative_path) = entry.enclosed_name().map(|path| path.to_owned()) else {
            continue;
        };
        let output_path = target_dir.join(relative_path);
        if entry.is_dir() {
            fs::create_dir_all(&output_path).map_err(|error| error.to_string())?;
        } else {
            if let Some(parent) = output_path.parent() {
                fs::create_dir_all(parent).map_err(|error| error.to_string())?;
            }
            let mut output = File::create(&output_path).map_err(|error| error.to_string())?;
            io::copy(&mut entry, &mut output).map_err(|error| error.to_string())?;
        }
        if index % 250 == 0 {
            set_status(
                app,
                &format!("首次启动正在解压本地运行环境... {index}/{total}"),
            );
        }
    }
    Ok(())
}

fn find_available_port(start: u16, end: u16) -> Result<u16, String> {
    for port in start..=end {
        if TcpListener::bind(("127.0.0.1", port)).is_ok() {
            return Ok(port);
        }
    }
    Err(format!("没有可用端口：{start}-{end}"))
}

fn wait_for_server(port: u16, timeout: Duration) -> bool {
    let started = Instant::now();
    while started.elapsed() < timeout {
        if is_http_ready(port) {
            return true;
        }
        thread::sleep(Duration::from_millis(500));
    }
    false
}

fn is_http_ready(port: u16) -> bool {
    let Ok(mut stream) = TcpStream::connect(("127.0.0.1", port)) else {
        return false;
    };
    let _ = stream.set_read_timeout(Some(Duration::from_secs(1)));
    let _ = stream.set_write_timeout(Some(Duration::from_secs(1)));

    if stream
        .write_all(b"GET / HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n")
        .is_err()
    {
        return false;
    }

    let mut buffer = [0_u8; 16];
    match stream.read(&mut buffer) {
        Ok(bytes_read) if bytes_read > 0 => buffer.starts_with(b"HTTP/"),
        _ => false,
    }
}

fn pipe_output<R>(label: &'static str, reader: R)
where
    R: io::Read + Send + 'static,
{
    thread::spawn(move || {
        let reader = BufReader::new(reader);
        for line in reader.lines().map_while(Result::ok) {
            println!("{label}: {line}");
        }
    });
}

fn set_status(app: &tauri::AppHandle, message: &str) {
    if let Some(window) = app.get_webview_window("main") {
        if let Ok(encoded) = serde_json::to_string(message) {
            let _ = window.eval(&format!("window.setStatus && window.setStatus({encoded})"));
        }
    }
}

fn stop_backend(app: &tauri::AppHandle) {
    let state = app.state::<BackendState>();
    let Ok(mut child) = state.child.lock() else {
        return;
    };
    if let Some(mut child) = child.take() {
        let _ = child.kill();
    }
}

fn local_data_home() -> PathBuf {
    std::env::var_os("LOCALAPPDATA")
        .map(PathBuf::from)
        .unwrap_or_else(std::env::temp_dir)
}

fn documents_home() -> PathBuf {
    std::env::var_os("USERPROFILE")
        .map(PathBuf::from)
        .map(|path| path.join("Documents"))
        .unwrap_or_else(|| local_data_home().join("Documents"))
}
