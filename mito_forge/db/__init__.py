"""
植物线粒体蛋白参考数据库模块

提供参考数据库路径管理和 BLAST 索引构建功能
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict

from ..utils.logging import get_logger
from ..utils.exceptions import ToolError

logger = get_logger("db")

PLANT_MITO_GENES: Dict[str, Dict[str, str]] = {
    "atp1": {
        "name": "atp1",
        "description": "ATP synthase subunit 1",
    },
    "atp4": {
        "name": "atp4",
        "description": "ATP synthase subunit 4",
    },
    "atp6": {
        "name": "atp6",
        "description": "ATP synthase subunit 6",
    },
    "atp8": {
        "name": "atp8",
        "description": "ATP synthase subunit 8",
    },
    "atp9": {
        "name": "atp9",
        "description": "ATP synthase subunit 9",
    },
    "ccmB": {
        "name": "ccmB",
        "description": "Cytochrome c biogenesis protein B",
    },
    "ccmC": {
        "name": "ccmC",
        "description": "Cytochrome c biogenesis protein C",
    },
    "ccmFc": {
        "name": "ccmFc",
        "description": "Cytochrome c biogenesis protein Fc",
    },
    "ccmFn": {
        "name": "ccmFn",
        "description": "Cytochrome c biogenesis protein Fn",
    },
    "cob": {
        "name": "cob",
        "description": "Cytochrome b",
    },
    "cox1": {
        "name": "cox1",
        "description": "Cytochrome c oxidase subunit 1",
    },
    "cox2": {
        "name": "cox2",
        "description": "Cytochrome c oxidase subunit 2",
    },
    "cox3": {
        "name": "cox3",
        "description": "Cytochrome c oxidase subunit 3",
    },
    "matR": {
        "name": "matR",
        "description": "Maturase R",
    },
    "mttB": {
        "name": "mttB",
        "description": "Transport membrane protein B",
    },
    "nad1": {
        "name": "nad1",
        "description": "NADH dehydrogenase subunit 1",
    },
    "nad2": {
        "name": "nad2",
        "description": "NADH dehydrogenase subunit 2",
    },
    "nad3": {
        "name": "nad3",
        "description": "NADH dehydrogenase subunit 3",
    },
    "nad4": {
        "name": "nad4",
        "description": "NADH dehydrogenase subunit 4",
    },
    "nad4L": {
        "name": "nad4L",
        "description": "NADH dehydrogenase subunit 4L",
    },
    "nad5": {
        "name": "nad5",
        "description": "NADH dehydrogenase subunit 5",
    },
    "nad6": {
        "name": "nad6",
        "description": "NADH dehydrogenase subunit 6",
    },
    "nad7": {
        "name": "nad7",
        "description": "NADH dehydrogenase subunit 7",
    },
    "nad9": {
        "name": "nad9",
        "description": "NADH dehydrogenase subunit 9",
    },
    "rpl5": {
        "name": "rpl5",
        "description": "Ribosomal protein L5",
    },
    "rpl16": {
        "name": "rpl16",
        "description": "Ribosomal protein L16",
    },
    "rps3": {
        "name": "rps3",
        "description": "Ribosomal protein S3",
    },
    "rps4": {
        "name": "rps4",
        "description": "Ribosomal protein S4",
    },
    "rps12": {
        "name": "rps12",
        "description": "Ribosomal protein S12",
    },
    "sdh3": {
        "name": "sdh3",
        "description": "Succinate dehydrogenase subunit 3",
    },
    "sdh4": {
        "name": "sdh4",
        "description": "Succinate dehydrogenase subunit 4",
    },
}


def get_db_path(db_name: str) -> Path:
    """
    获取数据库文件路径

    优先使用 MITO_DB_DIR 环境变量指定的目录，
    否则回退到 ~/.mito-forge/db/。
    如果目标位置不存在数据库文件，则从包内捆绑数据复制。

    Args:
        db_name: 数据库文件名，如 "plant_mito_proteins.fasta"

    Returns:
        数据库文件的绝对路径

    Raises:
        FileNotFoundError: 源数据库文件在包内也不存在时
    """
    env_dir = os.environ.get("MITO_DB_DIR")
    if env_dir:
        db_dir = Path(env_dir)
    else:
        db_dir = Path.home() / ".mito-forge" / "db"

    db_dir.mkdir(parents=True, exist_ok=True)
    target_path = db_dir / db_name

    if target_path.exists():
        return target_path

    bundled_path = Path(__file__).parent / db_name
    if not bundled_path.exists():
        raise FileNotFoundError(
            f"数据库文件 '{db_name}' 在目标目录和包内均不存在"
        )

    logger.info(f"从包内复制数据库文件: {bundled_path} -> {target_path}")
    shutil.copy2(bundled_path, target_path)
    return target_path


def ensure_blast_db(db_path: Path) -> Path:
    """
    确保 BLAST 数据库索引存在，如不存在则运行 makeblastdb 构建

    Args:
        db_path: FASTA 数据库文件路径

    Returns:
        BLAST 数据库前缀路径（不含 .phr/.pin/.psq 等后缀）

    Raises:
        ToolError: makeblastdb 执行失败时
        FileNotFoundError: FASTA 文件不存在时
    """
    if not db_path.exists():
        raise FileNotFoundError(f"FASTA 数据库文件不存在: {db_path}")

    db_prefix = db_path.with_suffix("")
    index_extensions = [".phr", ".pin", ".psq"]
    index_exists = all((db_prefix.with_suffix(ext)).exists() for ext in index_extensions)

    if index_exists:
        logger.debug(f"BLAST 索引已存在: {db_prefix}")
        return db_prefix

    makeblastdb = shutil.which("makeblastdb")
    if not makeblastdb:
        raise ToolError(
            "makeblastdb 未找到，请安装 BLAST+ 工具包: "
            "conda install -c bioconda blast"
        )

    cmd = [
        makeblastdb,
        "-in", str(db_path),
        "-dbtype", "prot",
        "-out", str(db_prefix),
        "-parse_seqids",
    ]

    logger.info(f"正在构建 BLAST 索引: {db_path}")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
        logger.debug(f"makeblastdb 输出: {result.stdout}")
    except subprocess.CalledProcessError as e:
        raise ToolError(
            f"makeblastdb 执行失败 (返回码 {e.returncode}): {e.stderr}"
        ) from e

    return db_prefix


__all__ = [
    "PLANT_MITO_GENES",
    "get_db_path",
    "ensure_blast_db",
]
