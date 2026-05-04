from __future__ import annotations

import argparse
import base64
import io
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image


DEFAULT_PROMPT = """请识别这页英文论文内容，并直接翻译成中文。
要求：保留公式的 LaTeX 表达，表格尽量输出 Markdown 表格，标题和段落层级尽量保留。只输出译文。"""


def render_input(path: Path, page: int, dpi: int) -> Image.Image:
    if path.suffix.lower() == ".pdf":
        import fitz

        with fitz.open(path) as document:
            if page < 1 or page > document.page_count:
                raise ValueError(f"page must be between 1 and {document.page_count}")
            pdf_page = document[page - 1]
            zoom = dpi / 72.0
            pixmap = pdf_page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            return Image.open(io.BytesIO(pixmap.pil_tobytes(format="PNG"))).convert("RGB")
    return Image.open(path).convert("RGB")


def image_to_data_url(image: Image.Image) -> str:
    with io.BytesIO() as buffer:
        image.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{encoded}"


def request_json(url: str, payload: dict | None = None, timeout: int = 600) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="GET" if payload is None else "POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {error.code}: {body}") from error


def get_model_name(server_url: str) -> str:
    models_url = f"{server_url.rstrip('/')}/v1/models"
    data = request_json(models_url, timeout=30)
    models = data.get("data") or []
    if not models:
        raise RuntimeError(f"no models returned from {models_url}")
    model_id = models[0].get("id")
    if not model_id:
        raise RuntimeError(f"model id missing in response from {models_url}")
    return model_id


def run_prompt(args: argparse.Namespace) -> str:
    input_path = Path(args.input)
    image = render_input(input_path, args.page, args.dpi)
    model_name = args.model or get_model_name(args.server_url)
    user_content = [
        {"type": "text", "text": args.prompt},
        {"type": "image_url", "image_url": {"url": image_to_data_url(image)}},
    ] if args.text_before_image else [
        {"type": "image_url", "image_url": {"url": image_to_data_url(image)}},
        {"type": "text", "text": args.prompt},
    ]
    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "user",
                "content": user_content,
            }
        ],
        "temperature": 0,
        "top_p": 0.01,
        "top_k": 1,
        "max_tokens": args.max_tokens,
        "skip_special_tokens": False,
        "vllm_xargs": {"no_repeat_ngram_size": 100},
    }
    chat_url = f"{args.server_url.rstrip('/')}/v1/chat/completions"
    response = request_json(chat_url, payload, timeout=args.timeout)
    choices = response.get("choices") or []
    if not choices:
        raise RuntimeError(f"no choices in response: {response}")
    message = choices[0].get("message") or {}
    return message.get("content") or ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Test a custom translation prompt against a MinerU vLLM OpenAI-compatible server.")
    parser.add_argument("input", help="PDF or image path to send to the VLM")
    parser.add_argument("--server-url", default="http://127.0.0.1:8000")
    parser.add_argument("--model", default="", help="Model name from /v1/models. Auto-detected when omitted.")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--prompt-file", default="", help="UTF-8 text file containing the prompt. Overrides --prompt when provided.")
    parser.add_argument("--text-before-image", action="store_true", help="Send the prompt before the image in the multimodal message.")
    parser.add_argument("--page", type=int, default=1, help="1-based PDF page number")
    parser.add_argument("--dpi", type=int, default=160, help="PDF render DPI for prompt tests")
    parser.add_argument("--max-tokens", type=int, default=2048)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--output", default="", help="Optional output text file")
    args = parser.parse_args()

    if args.prompt_file:
        args.prompt = Path(args.prompt_file).read_text(encoding="utf-8")

    try:
        result = run_prompt(args)
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    if args.output:
        Path(args.output).write_text(result, encoding="utf-8")
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())