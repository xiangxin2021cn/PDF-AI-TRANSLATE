"""本地存储管理器 - 管理翻译项目和文件的本地存储"""
from __future__ import annotations

import json
import logging
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class StorageManager:
    """本地存储管理器
    
    功能:
    - 创建和管理翻译项目
    - 存储源文件和翻译结果
    - 提供项目索引和检索
    - 支持文件浏览和预览
    
    目录结构:
    output/
    ├── projects/
    │   ├── {project_id}/
    │   │   ├── source.pdf           # 源文件
    │   │   ├── metadata.json        # 项目元数据
    │   │   ├── babeldoc/            # BabelDOC输出
    │   │   │   ├── translated.pdf   # 翻译稿
    │   │   │   ├── dual.pdf         # 对比稿
    │   │   │   └── vocabulary.txt   # 词汇表
    │   │   └── mineru/              # MinerU输出
    │   │       ├── translated.md    # Markdown翻译稿
    │   │       ├── translated.pdf   # A4 PDF翻译稿
    │   │       ├── dual.md          # Markdown对比稿
    │   │       ├── translated.html  # HTML翻译稿
    │   │       ├── dual.html        # HTML对比稿
    │   │       └── images/          # 提取的图片
    └── index.json                   # 项目索引
    """
    
    def __init__(self, storage_root: str | Path = "output"):
        """初始化存储管理器
        
        Args:
            storage_root: 存储根目录,默认为'output'
        """
        self.storage_root = Path(storage_root)
        self.projects_dir = self.storage_root / "projects"
        self.index_file = self.storage_root / "index.json"
        
        # 创建目录结构
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化索引
        if not self.index_file.exists():
            self._save_index({})
        
        logger.info(f"存储管理器初始化: {self.storage_root}")
    
    def create_project(
        self,
        source_pdf: str | Path,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """创建新的翻译项目
        
        Args:
            source_pdf: 源PDF文件路径
            metadata: 项目元数据,如:
                {
                    'title': '文档标题',
                    'lang_in': 'en',
                    'lang_out': 'zh',
                    'translation_path': 'babeldoc' | 'mineru',
                    'output_formats': ['pdf', 'md', 'html'],
                }
        
        Returns:
            project_id: 项目唯一ID
        """
        source_pdf = Path(source_pdf)
        
        if not source_pdf.exists():
            raise FileNotFoundError(f"源文件不存在: {source_pdf}")
        
        # 生成项目ID
        project_id = self._generate_project_id()
        project_dir = self.projects_dir / project_id
        
        # 创建项目目录结构
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "babeldoc").mkdir(exist_ok=True)
        (project_dir / "mineru").mkdir(exist_ok=True)
        (project_dir / "mineru" / "images").mkdir(exist_ok=True)
        
        # 复制源文件
        dest_source = project_dir / "source.pdf"
        shutil.copy2(source_pdf, dest_source)
        
        # 构建完整元数据
        full_metadata = {
            'project_id': project_id,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'source_file': source_pdf.name,
            'source_size': source_pdf.stat().st_size,
            'status': 'created',
            'title': metadata.get('title', source_pdf.stem) if metadata else source_pdf.stem,
            'lang_in': metadata.get('lang_in', 'en') if metadata else 'en',
            'lang_out': metadata.get('lang_out', 'zh') if metadata else 'zh',
            'translation_path': metadata.get('translation_path', 'babeldoc') if metadata else 'babeldoc',
            'output_formats': metadata.get('output_formats', ['pdf']) if metadata else ['pdf'],
        }
        
        # 添加用户自定义元数据
        if metadata:
            for key, value in metadata.items():
                if key not in full_metadata:
                    full_metadata[key] = value
        
        # 保存元数据
        self._save_metadata(project_id, full_metadata)
        
        # 更新索引
        self._update_index(project_id, full_metadata)
        
        logger.info(f"创建项目: {project_id} - {full_metadata['title']}")
        
        return project_id
    
    def save_result(
        self,
        project_id: str,
        path_type: str,
        file_name: str,
        content: bytes | str,
    ) -> Path:
        """保存翻译结果文件
        
        Args:
            project_id: 项目ID
            path_type: 路径类型,'babeldoc'或'mineru'
            file_name: 文件名,如'translated.pdf', 'dual.md'
            content: 文件内容(bytes或str)
        
        Returns:
            保存的文件路径
        """
        project_dir = self.projects_dir / project_id
        
        if not project_dir.exists():
            raise ValueError(f"项目不存在: {project_id}")
        
        # 确定保存路径
        if path_type not in ['babeldoc', 'mineru']:
            raise ValueError(f"无效的路径类型: {path_type}")
        
        save_dir = project_dir / path_type
        save_path = save_dir / file_name
        
        # 保存文件
        if isinstance(content, bytes):
            save_path.write_bytes(content)
        else:
            save_path.write_text(content, encoding='utf-8')
        
        # 更新元数据
        metadata = self.get_project(project_id)
        if 'results' not in metadata:
            metadata['results'] = {}
        if path_type not in metadata['results']:
            metadata['results'][path_type] = []
        
        if file_name not in metadata['results'][path_type]:
            metadata['results'][path_type].append(file_name)
        
        metadata['updated_at'] = datetime.now().isoformat()
        self._save_metadata(project_id, metadata)
        
        logger.info(f"保存结果: {project_id}/{path_type}/{file_name}")
        
        return save_path
    
    def save_image(
        self,
        project_id: str,
        image_name: str,
        image_data: bytes,
    ) -> Path:
        """保存图片文件
        
        Args:
            project_id: 项目ID
            image_name: 图片文件名
            image_data: 图片数据
        
        Returns:
            保存的图片路径
        """
        project_dir = self.projects_dir / project_id
        images_dir = project_dir / "mineru" / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        
        image_path = images_dir / image_name
        image_path.write_bytes(image_data)
        
        logger.info(f"保存图片: {project_id}/mineru/images/{image_name}")
        
        return image_path
    
    def get_project(self, project_id: str) -> Dict[str, Any]:
        """获取项目详情
        
        Args:
            project_id: 项目ID
        
        Returns:
            项目元数据
        """
        metadata_file = self.projects_dir / project_id / "metadata.json"
        
        if not metadata_file.exists():
            raise ValueError(f"项目不存在: {project_id}")
        
        return json.loads(metadata_file.read_text(encoding='utf-8'))
    
    def list_projects(
        self,
        filters: Optional[Dict[str, Any]] = None,
        sort_by: str = 'created_at',
        reverse: bool = True,
    ) -> List[Dict[str, Any]]:
        """列出所有项目
        
        Args:
            filters: 过滤条件,如{'lang_out': 'zh', 'status': 'completed'}
            sort_by: 排序字段,默认按创建时间
            reverse: 是否倒序,默认True(最新的在前)
        
        Returns:
            项目列表
        """
        index = self._load_index()
        projects = list(index.values())
        
        # 应用过滤器
        if filters:
            filtered_projects = []
            for project in projects:
                match = True
                for key, value in filters.items():
                    if project.get(key) != value:
                        match = False
                        break
                if match:
                    filtered_projects.append(project)
            projects = filtered_projects
        
        # 排序
        if sort_by in ['created_at', 'updated_at']:
            projects.sort(
                key=lambda x: x.get(sort_by, ''),
                reverse=reverse
            )
        
        return projects
    
    def get_file_path(self, project_id: str, relative_path: str) -> Path:
        """获取项目文件的完整路径
        
        Args:
            project_id: 项目ID
            relative_path: 相对路径,如'babeldoc/translated.pdf'
        
        Returns:
            完整文件路径
        """
        return self.projects_dir / project_id / relative_path
    
    def delete_project(self, project_id: str):
        """删除项目
        
        Args:
            project_id: 项目ID
        """
        project_dir = self.projects_dir / project_id
        
        if project_dir.exists():
            shutil.rmtree(project_dir)
        
        # 更新索引
        index = self._load_index()
        if project_id in index:
            del index[project_id]
            self._save_index(index)
        
        logger.info(f"删除项目: {project_id}")
    
    def update_project_status(self, project_id: str, status: str, **kwargs):
        """更新项目状态
        
        Args:
            project_id: 项目ID
            status: 新状态,如'processing', 'completed', 'failed'
            **kwargs: 其他要更新的字段
        """
        metadata = self.get_project(project_id)
        metadata['status'] = status
        metadata['updated_at'] = datetime.now().isoformat()
        
        for key, value in kwargs.items():
            metadata[key] = value
        
        self._save_metadata(project_id, metadata)
        self._update_index(project_id, metadata)
        
        logger.info(f"更新项目状态: {project_id} -> {status}")
    
    # ========== 私有方法 ==========
    
    def _generate_project_id(self) -> str:
        """生成唯一的项目ID"""
        return datetime.now().strftime("%Y%m%d_%H%M%S_") + str(uuid.uuid4())[:8]
    
    def _save_metadata(self, project_id: str, metadata: Dict[str, Any]):
        """保存项目元数据"""
        metadata_file = self.projects_dir / project_id / "metadata.json"
        metadata_file.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )
    
    def _load_index(self) -> Dict[str, Dict[str, Any]]:
        """加载项目索引"""
        if not self.index_file.exists():
            return {}
        return json.loads(self.index_file.read_text(encoding='utf-8'))
    
    def _save_index(self, index: Dict[str, Dict[str, Any]]):
        """保存项目索引"""
        self.index_file.write_text(
            json.dumps(index, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )
    
    def _update_index(self, project_id: str, metadata: Dict[str, Any]):
        """更新项目索引"""
        index = self._load_index()
        
        # 只保存关键信息到索引
        index[project_id] = {
            'project_id': metadata['project_id'],
            'title': metadata['title'],
            'created_at': metadata['created_at'],
            'updated_at': metadata['updated_at'],
            'status': metadata['status'],
            'lang_in': metadata['lang_in'],
            'lang_out': metadata['lang_out'],
            'translation_path': metadata['translation_path'],
            'source_file': metadata['source_file'],
        }
        
        self._save_index(index)

