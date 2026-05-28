# Mito-Forge RAG 系统重构设计文档

## 一、现状诊断

### 1.1 当前 RAG 架构

```
用户 Prompt
    │
    ▼
rag_augment() ──► ChromaDB.query() ──► 拼接到 Prompt 末尾
    │                    │
    │                    ▼
    │            HashEmbeddingFunction
    │          (字符 n-gram + SHA1 哈希)
    │                    │
    │                    ▼
    │            PersistentClient
    │          (~/.mito-forge/chroma)
    │                    │
    │                    ▼
    │            collection "knowledge"
    │          (⚠️ 从未被灌入数据)
    │
    ▼
增强后的 Prompt ──► LLM
```

### 1.2 核心问题清单

| # | 问题 | 严重程度 | 说明 |
|---|------|----------|------|
| 1 | **知识库为空** | 🔴 致命 | `core/knowledge/` 只有空 `__init__.py`，没有任何文档灌入逻辑，ChromaDB 的 `knowledge` 集合永远是空的，RAG 检索永远返回空列表 |
| 2 | **Embedding 无语义能力** | 🔴 致命 | `HashEmbeddingFunction` 基于字符 n-gram + SHA1 哈希，只能捕获字面相似性，无法理解语义（"SPAdes OOM" 和 "组装内存不足" 无法关联） |
| 3 | **无文档加载/分块管线** | 🔴 致命 | 没有从任何来源（PDF、网页、工具手册、FAQ）加载、清洗、分块、索引文档的代码 |
| 4 | **检索策略过于简单** | 🟡 严重 | 只做单次向量检索，无 re-ranking、无 query 改写、无多路召回 |
| 5 | **注入策略粗糙** | 🟡 严重 | 直接拼接到 prompt 末尾，无结构化引用、无相关性过滤、无 token 预算控制 |
| 6 | **Mem0 与 RAG 功能重叠** | 🟡 中等 | 两者都是"检索历史信息注入 prompt"，但存储和检索方式不同，容易造成 prompt 冗余 |
| 7 | **无评估体系** | 🟡 中等 | 没有检索质量评估（Hit Rate、MRR、NDCG），无法量化 RAG 的实际贡献 |

---

## 二、目标架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────┐
│                    知识源 (Knowledge Sources)              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│  │ 工具手册   │ │ 论文文档  │ │ 错误 FAQ  │ │ 运行经验  │   │
│  │ (Markdown)│ │ (PDF)    │ │ (YAML)   │ │ (JSON)   │   │
│  └─────┬────┘ └─────┬────┘ └─────┬────┘ └─────┬────┘   │
│        │            │            │            │          │
│        ▼            ▼            ▼            ▼          │
│  ┌──────────────────────────────────────────────────┐   │
│  │          文档加载管线 (Ingestion Pipeline)          │   │
│  │  Loader → Cleaner → Chunker → Enricher → Indexer │   │
│  └──────────────────────┬───────────────────────────┘   │
│                         │                                │
│                         ▼                                │
│  ┌──────────────────────────────────────────────────┐   │
│  │              向量存储 (Vector Store)               │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌──────────┐ │   │
│  │  │ tool_manuals │  │ domain_know  │  │ run_exp  │ │   │
│  │  │ (工具手册)    │  │ (领域知识)   │  │ (运行经验)│ │   │
│  │  └─────────────┘  └─────────────┘  └──────────┘ │   │
│  │         ChromaDB + sentence-transformers           │   │
│  └──────────────────────┬───────────────────────────┘   │
│                         │                                │
│                         ▼                                │
│  ┌──────────────────────────────────────────────────┐   │
│  │              检索管线 (Retrieval Pipeline)          │   │
│  │  Query → Rewrite → Multi-Recall → Rerank → Filter │   │
│  └──────────────────────┬───────────────────────────┘   │
│                         │                                │
│                         ▼                                │
│  ┌──────────────────────────────────────────────────┐   │
│  │              生成管线 (Generation Pipeline)         │   │
│  │  Context Assembly → Prompt Template → LLM → Parse │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### 2.2 设计原则

1. **语义优先**：Embedding 必须具备语义理解能力，这是 RAG 的核心价值
2. **离线可用**：所有模型和索引必须支持完全离线运行（Ollama + 本地 sentence-transformer）
3. **可评估**：每个环节都有量化指标，可以 A/B 测试不同配置
4. **渐进增强**：基础功能（BM25）零依赖可用，高级功能（语义 embedding + reranker）按需启用
5. **领域特化**：知识库内容聚焦线粒体基因组学，不做通用 RAG

---

## 三、详细设计

### 3.1 知识源设计 (Knowledge Sources)

#### 3.1.1 知识源分类与内容

**Collection 1: `tool_manuals`（工具手册）**

| 文档 | 来源 | 格式 | 条目数(估) | 用途 |
|------|------|------|-----------|------|
| SPAdes 手册 | github.com/ablab/spades | Markdown | ~50 | 组装参数选择、错误诊断 |
| Flye 手册 | github.com/fenderglass/Flye | Markdown | ~30 | ONT 组装参数、repeat 诊断 |
| MitoZ 文档 | github.com/linzhi2013/MitoZ | Markdown | ~20 | 动物线粒体组装参数 |
| GetOrganelle 文档 | github.com/Kinggerm/GetOrganelle | Markdown | ~20 | 细胞器基因组 baiting 参数 |
| NOVOPlasty 文档 | github.com/ndierckx/NOVOPlasty | Markdown | ~15 | 种子延伸参数 |
| PMGA 文档 | github.com/xul9625800/PMGA | Markdown | ~15 | 植物线粒体注释参数 |
| BLAST+ 手册 | NCBI | HTML→MD | ~40 | blastx 参数、数据库构建 |
| Pilon 文档 | github.com/broadinstitute/pilon | Markdown | ~15 | Illumina 抛光参数 |
| Racon/Medaka 文档 | github.com/lbcb-sci/racon | Markdown | ~20 | ONT 抛光参数 |
| tRNAscan-SE 手册 | github.com/UCSC-LoweLab/tRNAscan-SE | Markdown | ~10 | tRNA 预测参数 |

**Collection 2: `domain_knowledge`（领域知识）**

| 文档 | 来源 | 格式 | 条目数(估) | 用途 |
|------|------|------|-----------|------|
| 线粒体基因组学综述 | NCBI/Reviews | PDF→MD | ~30 | 物种特异性参数选择 |
| 动物线粒体标准基因集 | NCBI RefSeq | 表格 | ~10 | 注释完整性评估 |
| 植物线粒体标准基因集 | NCBI RefSeq | 表格 | ~10 | 注释完整性评估 |
| 遗传密码表 | NCBI | 表格 | ~5 | genetic_code 参数选择 |
| 组装质量评估标准 | QUAST/MitoZ 论文 | PDF→MD | ~15 | N50/覆盖度阈值 |
| 常见错误模式 FAQ | 自建 | YAML | ~30 | 错误诊断和自动修复 |

**Collection 3: `run_experience`（运行经验）**

| 文档 | 来源 | 格式 | 条目数(估) | 用途 |
|------|------|------|-----------|------|
| 历史运行摘要 | Mem0/JSON | JSON | 动态增长 | 相似数据集的参数推荐 |
| 错误诊断案例 | 自动积累 | JSON | 动态增长 | 相似错误的修复策略 |
| 参数调优记录 | 自动积累 | JSON | 动态增长 | 参数调整经验 |

#### 3.1.2 FAQ 知识库结构（YAML 格式）

```yaml
# knowledge/error_faq.yaml
- id: "spades_oom"
  category: "assembly"
  tool: "spades"
  error_pattern: "out of memory|OOM|Cannot allocate|bad_alloc"
  symptoms:
    - "SPAdes 在组装大基因组时崩溃"
    - "错误信息包含 'bad_alloc' 或 'out of memory'"
  root_cause: "SPAdes 默认内存配置不足以处理当前数据量"
  fix_strategy: "adjust_params"
  suggestions:
    - action: "减少线程数以降低峰值内存"
      params: {"threads": "max(1, current_threads // 2)"}
    - action: "启用 --careful 模式减少内存占用"
      params: {"careful": true}
    - action: "降低 K-mer 范围"
      params: {"k": "21,33,55"}
    - action: "如果仍然 OOM，切换到 Flye"
      alternative_tool: "flye"
  confidence: 0.95
  references: ["SPAdes manual §3.1", "Issue #1234"]

- id: "flye_repeat_resolution"
  category: "assembly"
  tool: "flye"
  error_pattern: "repeat resolution failed|unresolved repeats"
  symptoms:
    - "Flye 输出包含大量未解析的 repeat"
    - "组装图中有多个 disconnected components"
  root_cause: "ONT 数据覆盖度不足以解析 repeat 区域"
  fix_strategy: "adjust_params"
  suggestions:
    - action: "增加最小覆盖度阈值"
      params: {"min-overlap": "5000"}
    - action: "如果覆盖度 < 30x，建议增加测序深度"
      params: {}
    - action: "使用 Racon + Medaka 多轮抛光"
      params: {"polish_rounds": 3}
  confidence: 0.85

- id: "plant_annotation_low_gene_count"
  category: "annotation"
  tool: "pmga"
  error_pattern: "low gene count|few genes detected|incomplete annotation"
  symptoms:
    - "PMGA 注释的基因数远少于预期（< 20 蛋白编码基因）"
    - "植物线粒体基因组注释完整性 < 60%"
  root_cause: "输入序列可能不是完整的线粒体基因组，或物种不在 PMGA 参考库中"
  fix_strategy: "switch_tool"
  suggestions:
    - action: "尝试 MITOFY（基于 BLAST 同源搜索，覆盖面更广）"
      alternative_tool: "mitofy"
    - action: "尝试 BLAST+ 同源注释（最通用但精度最低）"
      alternative_tool: "blast"
    - action: "检查组装完整性（N50 是否接近预期基因组大小）"
      params: {}
  confidence: 0.80
```

### 3.2 文档加载管线 (Ingestion Pipeline)

#### 3.2.1 模块结构

```
mito_forge/core/knowledge/
├── __init__.py              # 公共接口
├── loader.py                # 文档加载器
├── chunker.py               # 文档分块器
├── enricher.py              # 元数据增强
├── indexer.py               # 向量索引构建
├── store.py                 # 向量存储管理
├── retriever.py             # 检索管线
├── evaluator.py             # 检索质量评估
└── sources/                 # 知识源文件
    ├── tool_manuals/        # 工具手册 (Markdown)
    ├── domain_knowledge/   # 领域知识
    └── error_faq.yaml       # 错误 FAQ
```

#### 3.2.2 Loader 设计

```python
# 知识源类型枚举
class SourceType(Enum):
    MARKDOWN = "markdown"
    YAML = "yaml"
    JSON = "json"
    PDF = "pdf"          # 需要 PyPDF2，可选依赖
    HTML = "html"        # 需要 beautifulsoup4，可选依赖

# 文档加载器接口
class BaseLoader(ABC):
    def load(self, source: Path) -> List[Document]: ...

class MarkdownLoader(BaseLoader):
    """加载 Markdown 文件，按标题层级拆分"""
    def load(self, source: Path) -> List[Document]:
        # 1. 读取 Markdown 文件
        # 2. 按标题层级拆分（# ## ### 为分割点）
        # 3. 保留标题作为元数据
        # 4. 返回 Document 列表

class YAMLLoader(BaseLoader):
    """加载 YAML 格式的 FAQ"""
    def load(self, source: Path) -> List[Document]:
        # 1. 解析 YAML
        # 2. 每个 FAQ 条目转为一个 Document
        # 3. error_pattern, symptoms, fix_strategy 作为元数据

class JSONLoader(BaseLoader):
    """加载 JSON 格式的运行经验"""
    def load(self, source: Path) -> List[Document]:
        # 1. 解析 JSON
        # 2. 每条经验转为一个 Document
        # 3. tags, timestamp, agent 作为元数据

# Document 数据结构
@dataclass
class Document:
    content: str                    # 文档内容
    metadata: Dict[str, Any]        # 元数据
    source: str                     # 来源文件路径
    doc_id: str                     # 文档唯一 ID（用于去重）
```

#### 3.2.3 Chunker 设计

```python
class ChunkingStrategy(Enum):
    FIXED_SIZE = "fixed_size"           # 固定大小分块
    SEMANTIC = "semantic"               # 按语义边界分块
    HEADING_BASED = "heading_based"     # 按标题层级分块（Markdown 专用）

class DocumentChunker:
    """
    文档分块策略

    选择理由：
    - 工具手册：按标题层级分块（heading_based），保持章节完整性
    - FAQ：无需分块，每条 FAQ 已经是最小语义单元
    - 论文：固定大小 + 重叠（fixed_size），因为 PDF 转换后无标题结构
    """

    def __init__(self,
                 strategy: ChunkingStrategy = ChunkingStrategy.HEADING_BASED,
                 chunk_size: int = 512,        # 目标分块大小（字符数）
                 chunk_overlap: int = 64,      # 重叠字符数
                 min_chunk_size: int = 100):   # 最小分块大小
        ...

    def chunk(self, doc: Document) -> List[Chunk]:
        ...

@dataclass
class Chunk:
    content: str                    # 分块内容
    metadata: Dict[str, Any]        # 继承自 Document + 分块位置信息
    chunk_id: str                   # 分块唯一 ID
    parent_doc_id: str              # 父文档 ID
    position: int                   # 在父文档中的位置
```

#### 3.2.4 Enricher 设计

```python
class MetadataEnricher:
    """
    元数据增强：为每个 Chunk 添加结构化的元数据标签

    增强维度：
    1. tool_name: 涉及的工具名称（从内容中提取）
    2. category: 知识类别（assembly/annotation/qc/polish/error_handling）
    3. kingdom: 适用的物种类型（animal/plant/both）
    4. platform: 适用的测序平台（illumina/nanopore/pacbio/both）
    5. error_type: 涉及的错误类型（如果是 FAQ）
    """

    TOOL_KEYWORDS = {
        "spades": ["spades", "spades.py"],
        "flye": ["flye"],
        "mitoz": ["mitoz"],
        "getorganelle": ["getorganelle"],
        "pmga": ["pmga"],
        "mitofy": ["mitofy"],
        "blast": ["blastx", "blastn", "makeblastdb"],
        "pilon": ["pilon"],
        "racon": ["racon"],
        "medaka": ["medaka"],
    }

    CATEGORY_KEYWORDS = {
        "assembly": ["assemble", "contig", "scaffold", "N50", "kmer"],
        "annotation": ["annotate", "gene", "CDS", "tRNA", "rRNA", "GFF"],
        "qc": ["quality", "fastqc", "trim", "filter"],
        "polish": ["polish", "pilon", "racon", "medaka"],
        "error_handling": ["error", "fail", "oom", "timeout", "crash"],
    }

    def enrich(self, chunk: Chunk) -> Chunk:
        # 1. 从内容中提取工具名称
        # 2. 从内容中推断知识类别
        # 3. 从内容中推断适用物种/平台
        # 4. 添加到 metadata
        return enriched_chunk
```

#### 3.2.5 Indexer 设计

```python
class KnowledgeIndexer:
    """
    向量索引构建器

    Embedding 策略（渐进增强）：
    Level 0: BM25 关键词检索（零依赖，始终可用）
    Level 1: sentence-transformers/all-MiniLM-L6-v2（80MB，本地运行）
    Level 2: BAAI/bge-small-zh-v1.5（支持中英文，93MB，本地运行）
    Level 3: Ollama embedding API（nomic-embed-text，274MB，需 Ollama）

    检测优先级：Level 3 > Level 2 > Level 1 > Level 0
    """

    def __init__(self, store: VectorStore, embedding_level: str = "auto"):
        ...

    def index(self, chunks: List[Chunk]) -> int:
        """
        将 Chunks 索引到向量存储

        Returns:
            成功索引的 Chunk 数量
        """
        # 1. 检测可用的 embedding 级别
        # 2. 对每个 Chunk 生成 embedding
        # 3. 写入向量存储
        # 4. 返回索引数量

    def _detect_embedding_level(self) -> str:
        """
        自动检测可用的 embedding 级别

        检测顺序：
        1. 检查 Ollama 是否运行 + nomic-embed-text 模型是否可用
        2. 检查 sentence-transformers 是否安装
        3. 检查 bge-small-zh 是否可用
        4. 回退到 BM25
        """
```

### 3.3 向量存储设计 (Vector Store)

#### 3.3.1 存储架构

```python
class VectorStore:
    """
    统一的向量存储接口

    底层实现选择：
    - 首选：ChromaDB（已集成，支持 PersistentClient）
    - 备选：FAISS（纯本地，无需服务，但需要手动管理持久化）

    多 Collection 设计：
    - tool_manuals: 工具手册索引
    - domain_knowledge: 领域知识索引
    - run_experience: 运行经验索引

    为什么分 Collection：
    1. 不同知识源的检索策略不同（工具手册需要精确匹配，领域知识需要语义检索）
    2. 可以按 Collection 设置不同的 top_k
    3. 可以独立更新某个 Collection 而不影响其他
    """

    def __init__(self, persist_dir: Path, embedding_fn):
        self.client = chromadb.PersistentClient(path=str(persist_dir))
        self.collections = {
            "tool_manuals": self._get_or_create_collection("tool_manuals", ...),
            "domain_knowledge": self._get_or_create_collection("domain_knowledge", ...),
            "run_experience": self._get_or_create_collection("run_experience", ...),
        }

    def query(self,
              collection_name: str,
              query_text: str,
              n_results: int = 5,
              filter_metadata: Dict = None) -> List[SearchResult]:
        """
        查询向量存储

        Args:
            collection_name: Collection 名称
            query_text: 查询文本
            n_results: 返回结果数
            filter_metadata: 元数据过滤条件（如 {"tool_name": "spades"}）
        """
```

#### 3.3.2 Embedding 函数设计

```python
class EmbeddingFunction(Protocol):
    """Embedding 函数接口"""
    def embed_documents(self, texts: List[str]) -> List[List[float]]: ...
    def embed_query(self, text: str) -> List[float]: ...

class SentenceTransformerEmbedding:
    """
    基于 sentence-transformers 的语义 Embedding

    推荐模型：
    - all-MiniLM-L6-v2: 80MB, 384维, 英文为主, 速度快
    - bge-small-zh-v1.5: 93MB, 512维, 中英文, 适合中文场景
    - nomic-embed-text: 274MB, 768维, 需通过 Ollama API

    为什么选这些模型：
    - 全部支持本地运行，无需 API 调用
    - 模型小（< 300MB），首次下载后缓存
    - 在 MTEB benchmark 上表现优秀
    - 与 ChromaDB 原生兼容
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model_name)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self.model.encode(texts, show_progress_bar=False).tolist()

    def embed_query(self, text: str) -> List[float]:
        return self.model.encode([text], show_progress_bar=False)[0].tolist()

class BM25Embedding:
    """
    BM25 关键词检索的 Embedding 适配器

    当 sentence-transformers 不可用时的零依赖回退方案。
    不是真正的 embedding，而是将 BM25 检索结果包装为
    与向量检索相同的接口，便于统一调用。

    实现方式：
    - 对 query 做 jieba 分词
    - 对每个文档也做分词并建立倒排索引
    - 用 BM25 算法计算相关性
    - 包装为与向量检索相同的返回格式
    """

    def __init__(self):
        import jieba  # 可选依赖
        ...
```

### 3.4 检索管线设计 (Retrieval Pipeline)

#### 3.4.1 多路召回

```python
class MultiRecallRetriever:
    """
    多路召回检索器

    召回路径：
    1. 语义向量召回（sentence-transformer embedding + cosine similarity）
    2. 关键词召回（BM25 / ChromaDB where filter）
    3. 元数据精确匹配（tool_name, category, kingdom 等结构化字段）

    为什么需要多路召回：
    - 语义召回：能理解"内存不足"和"OOM"是同一个意思
    - 关键词召回：对精确的工具名、参数名匹配更可靠
    - 元数据匹配：当 Agent 明确知道当前使用什么工具时，直接过滤

    融合策略：Reciprocal Rank Fusion (RRF)
    - 每路召回的结果按排名赋分：score = 1 / (k + rank)
    - 同一文档的多路得分相加
    - 按总分排序
    """

    def retrieve(self,
                 query: str,
                 context: RetrievalContext,
                 top_k: int = 5) -> List[RetrievalResult]:
        """
        多路召回 + 融合

        Args:
            query: 查询文本
            context: 检索上下文（包含当前工具、物种类型等元数据）
            top_k: 返回结果数
        """
        # 1. 语义向量召回
        semantic_results = self._semantic_recall(query, top_k * 3)

        # 2. 关键词召回
        keyword_results = self._keyword_recall(query, top_k * 3)

        # 3. 元数据精确匹配
        metadata_results = self._metadata_recall(context, top_k * 2)

        # 4. RRF 融合
        fused = self._rrf_fusion(
            [semantic_results, keyword_results, metadata_results],
            k=60  # RRF 参数
        )

        return fused[:top_k]
```

#### 3.4.2 检索上下文

```python
@dataclass
class RetrievalContext:
    """
    检索上下文：Agent 在检索时提供的结构化信息

    用途：
    1. 作为元数据过滤条件（只检索与当前工具/物种相关的文档）
    2. 作为 query 改写的依据（结合当前任务描述改写查询）
    3. 作为相关性判断的参考
    """
    agent_name: str              # 当前 Agent 名称
    current_tool: Optional[str]  # 当前使用的工具
    kingdom: Optional[str]       # 当前物种类型
    platform: Optional[str]      # 当前测序平台
    error_type: Optional[str]    # 当前错误类型（如果是错误诊断场景）
    task_description: Optional[str]  # 当前任务描述
```

#### 3.4.3 Query 改写

```python
class QueryRewriter:
    """
    查询改写器

    目的：将 Agent 的内部查询（可能是 stderr 片段、简短关键词）
    改写为更适合检索的查询。

    策略：
    1. 关键词提取：从 stderr 中提取关键错误信息
    2. 同义扩展：将缩写扩展为全称（OOM → out of memory）
    3. 上下文注入：结合 RetrievalContext 添加工具名和物种信息

    示例：
    - 原始查询: "bad_alloc SPAdes"
    - 改写后: "SPAdes assembly out of memory error solution"
    - 原始查询: "注释基因太少"
    - 改写后: "plant mitochondrial annotation low gene count PMGA MITOFY"
    """

    SYNONYM_MAP = {
        "oom": "out of memory",
        "bad_alloc": "out of memory",
        "segfault": "segmentation fault",
        "timeout": "execution timeout",
        "注释": "annotation",
        "组装": "assembly",
        "内存不足": "out of memory",
    }

    def rewrite(self, query: str, context: RetrievalContext) -> str:
        # 1. 同义扩展
        # 2. 上下文注入（添加工具名、物种类型）
        # 3. 去除噪声（stderr 中的行号、路径等）
        return rewritten_query
```

#### 3.4.4 Re-ranker

```python
class ReRanker:
    """
    重排序器

    对多路召回融合后的结果进行精细重排序。

    策略（渐进增强）：
    Level 0: 无重排序（直接使用 RRF 分数）
    Level 1: 基于规则的重排序（元数据匹配度加分）
    Level 2: LLM-based 重排序（用 LLM 判断文档与查询的相关性）
    Level 3: Cross-encoder 重排序（bge-reranker-base，需要额外模型）

    为什么需要重排序：
    - 向量检索是双塔模型（query 和 doc 独立编码），精度有限
    - Cross-encoder 是交互式模型（query 和 doc 一起编码），精度更高
    - 但 Cross-encoder 速度慢，只适合对少量候选结果重排序
    """

    def rerank(self,
               query: str,
               results: List[RetrievalResult],
               top_k: int = 5) -> List[RetrievalResult]:
        ...
```

### 3.5 生成管线设计 (Generation Pipeline)

#### 3.5.1 上下文组装

```python
class ContextAssembler:
    """
    上下文组装器

    将检索到的文档组装为结构化的上下文，注入到 Prompt 中。

    设计要点：
    1. Token 预算控制：总上下文不超过 max_context_tokens
    2. 相关性过滤：只保留相关性分数 > threshold 的文档
    3. 去重：相似度 > 0.9 的文档只保留一个
    4. 结构化引用：每个引用包含来源、相关性分数、内容摘要
    5. 优先级：当 token 预算不足时，按相关性分数排序截断
    """

    def assemble(self,
                 query: str,
                 results: List[RetrievalResult],
                 max_context_tokens: int = 2000,
                 relevance_threshold: float = 0.3) -> str:
        """
        组装上下文

        输出格式：
        ---
        ## 参考资料

        [1] SPAdes 手册 §3.1 - 内存配置
        相关性: 0.92 | 来源: tool_manuals
        SPAdes 默认使用 250GB 内存上限。对于大基因组，建议使用
        --memory 参数限制内存使用，或减少线程数...

        [2] 错误 FAQ: SPAdes OOM
        相关性: 0.88 | 来源: domain_knowledge
        当 SPAdes 报告 bad_alloc 错误时，表示内存不足...
        ---
        """
```

#### 3.5.2 与现有 Agent 的集成点

```python
# 修改 base_agent.py 中的 rag_augment 方法

def rag_augment(self, prompt: str, task=None, top_k=4):
    """
    RAG 增强入口（重构后）

    变更：
    1. 使用新的检索管线（多路召回 + RRF + 重排序）
    2. 使用结构化上下文组装（替代简单拼接）
    3. 传入 RetrievalContext（包含当前工具、物种等元数据）
    4. 返回结构化的引用信息（来源、相关性分数）
    """
    # 1. 构建 RetrievalContext
    context = RetrievalContext(
        agent_name=self.name,
        current_task=task,
        ...
    )

    # 2. 查询改写
    rewritten_query = self._query_rewriter.rewrite(prompt, context)

    # 3. 多路召回 + RRF 融合 + 重排序
    results = self._retriever.retrieve(rewritten_query, context, top_k=top_k)

    # 4. 上下文组装
    context_text = self._context_assembler.assemble(
        query=prompt,
        results=results,
        max_context_tokens=self.config.get("rag_max_tokens", 2000)
    )

    # 5. 注入到 prompt
    if context_text:
        augmented = f"{prompt}\n\n{context_text}"
    else:
        augmented = prompt

    # 6. 构建引用列表
    citations = [
        {
            "source": r.metadata.get("source", "unknown"),
            "relevance": r.score,
            "snippet": r.content[:200],
        }
        for r in results
    ]

    return augmented, citations
```

### 3.6 Mem0 与 RAG 的统一

#### 3.6.1 当前问题

- Mem0 和 RAG 功能重叠：都是"检索信息注入 prompt"
- Mem0 是外部依赖，大多数环境不可用
- Mem0 和 RAG 的检索结果可能重复

#### 3.6.2 统一方案

```
┌──────────────────────────────────────────────┐
│              统一检索接口                       │
│          retrieve(query, context)             │
│                    │                          │
│         ┌─────────┼─────────┐                │
│         ▼         ▼         ▼                │
│   ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│   │ RAG 检索  │ │ 经验检索  │ │ 规则匹配  │   │
│   │(ChromaDB)│ │(JSON文件) │ │(YAML FAQ)│   │
│   └──────────┘ └──────────┘ └──────────┘   │
│         │         │         │                │
│         └─────────┼─────────┘                │
│                   ▼                          │
│           RRF 融合 + 去重                     │
│                   │                          │
│                   ▼                          │
│           结构化上下文输出                     │
└──────────────────────────────────────────────┘
```

**具体变更**：
1. **去掉 Mem0 依赖**：将运行经验存储为 JSON 文件（`~/.mito-forge/experience/`），用 ChromaDB 的 `run_experience` Collection 索引
2. **统一检索入口**：`memory_query` 和 `rag_augment` 合并为一个 `retrieve` 方法
3. **经验写入**：`memory_write` 改为写入 JSON 文件 + 自动索引到 ChromaDB
4. **经验格式**：每条经验包含 `tags`, `summary`, `metrics`, `timestamp`, `agent_name`

### 3.7 评估体系设计

#### 3.7.1 检索质量评估

```python
class RetrievalEvaluator:
    """
    检索质量评估器

    评估指标：
    1. Hit Rate: 查询返回的结果中包含相关文档的比例
    2. MRR (Mean Reciprocal Rank): 第一个相关文档排名的倒数的均值
    3. NDCG@k: 考虑排序位置的归一化折损累积增益
    4. Latency: 检索延迟（ms）

    评估数据集：
    - 预构建的 (query, relevant_doc_ids) 对
    - 从 FAQ 中自动生成（每个 FAQ 条目的 symptoms 作为 query，该条目作为 relevant）
    - 从历史运行日志中提取（Agent 的查询 + 实际有用的文档）
    """

    EVALUATION_QUERIES = [
        {
            "query": "SPAdes 组装时内存不足怎么办",
            "relevant_ids": ["spades_oom", "spades_manual_memory"],
            "context": {"tool": "spades", "category": "assembly"}
        },
        {
            "query": "植物线粒体注释基因太少",
            "relevant_ids": ["plant_annotation_low_gene_count", "pmga_manual_params"],
            "context": {"tool": "pmga", "category": "annotation", "kingdom": "plant"}
        },
        ...
    ]
```

#### 3.7.2 端到端评估

```python
class EndToEndEvaluator:
    """
    端到端 RAG 评估

    评估 RAG 对 Agent 决策质量的实际影响。

    方法：消融实验
    - 实验组：Agent + RAG（完整检索增强）
    - 对照组 1：Agent + 无 RAG（去掉检索增强）
    - 对照组 2：Agent + Hash Embedding RAG（当前方案）
    - 对照组 3：Agent + BM25 RAG（仅关键词检索）

    评估维度：
    1. 错误诊断准确率：LLM 诊断与实际错误类型的匹配度
    2. 修复策略有效性：Agent 自动修复后流水线是否成功
    3. 参数推荐合理性：推荐的参数是否在合理范围内
    4. 注释质量评估分数：RAG 增强后的注释分析质量
    """
```

---

## 四、实施步骤

### Phase 1: 基础设施（知识库 + Embedding）

| 步骤 | 内容 | 涉及文件 | 依赖 |
|------|------|----------|------|
| 1.1 | 创建知识源目录和初始文档 | `knowledge/sources/` | 无 |
| 1.2 | 编写错误 FAQ YAML | `knowledge/sources/error_faq.yaml` | 无 |
| 1.3 | 下载/整理工具手册 Markdown | `knowledge/sources/tool_manuals/` | 无 |
| 1.4 | 实现 Document/Chunk 数据结构 | `knowledge/__init__.py` | 无 |
| 1.5 | 实现 MarkdownLoader | `knowledge/loader.py` | 无 |
| 1.6 | 实现 YAMLLoader | `knowledge/loader.py` | 无 |
| 1.7 | 实现 HeadingBasedChunker | `knowledge/chunker.py` | 无 |
| 1.8 | 实现 MetadataEnricher | `knowledge/enricher.py` | 无 |
| 1.9 | 实现 SentenceTransformerEmbedding | `knowledge/store.py` | sentence-transformers |
| 1.10 | 实现 BM25Embedding（回退方案） | `knowledge/store.py` | jieba（可选） |
| 1.11 | 实现 KnowledgeIndexer | `knowledge/indexer.py` | ChromaDB |
| 1.12 | 实现 `mito-forge knowledge index` CLI 命令 | `cli/commands/knowledge.py` | 无 |

### Phase 2: 检索管线

| 步骤 | 内容 | 涉及文件 | 依赖 |
|------|------|----------|------|
| 2.1 | 实现 RetrievalContext | `knowledge/retriever.py` | 无 |
| 2.2 | 实现 QueryRewriter | `knowledge/retriever.py` | 无 |
| 2.3 | 实现 MultiRecallRetriever | `knowledge/retriever.py` | Phase 1 |
| 2.4 | 实现 RRF 融合 | `knowledge/retriever.py` | 无 |
| 2.5 | 实现 ReRanker（规则 + LLM） | `knowledge/retriever.py` | LLM |
| 2.6 | 实现 ContextAssembler | `knowledge/retriever.py` | 无 |

### Phase 3: Agent 集成

| 步骤 | 内容 | 涉及文件 | 依赖 |
|------|------|----------|------|
| 3.1 | 重构 base_agent.rag_augment | `core/agents/base_agent.py` | Phase 2 |
| 3.2 | 去掉 Mem0 依赖，用 JSON 文件 + ChromaDB 替代 | `core/agents/base_agent.py` | Phase 1 |
| 3.3 | 更新所有 Agent 的 RAG 调用 | `core/agents/*.py` | Phase 3.1 |
| 3.4 | 更新 doctor 命令检查 RAG 状态 | `cli/commands/doctor.py` | Phase 1 |

### Phase 4: 评估与优化

| 步骤 | 内容 | 涉及文件 | 依赖 |
|------|------|----------|------|
| 4.1 | 构建评估数据集 | `knowledge/eval_dataset.json` | 无 |
| 4.2 | 实现 RetrievalEvaluator | `knowledge/evaluator.py` | Phase 2 |
| 4.3 | 实现 EndToEndEvaluator | `knowledge/evaluator.py` | Phase 3 |
| 4.4 | 运行消融实验，收集数据 | `benchmark/` | Phase 4.3 |
| 4.5 | 优化 Embedding 模型选择 | `knowledge/store.py` | Phase 4.4 |
| 4.6 | 优化分块策略和检索参数 | `knowledge/` | Phase 4.4 |

---

## 五、关键设计决策与理由

### 5.1 为什么选择 ChromaDB 而不是 FAISS

| 维度 | ChromaDB | FAISS |
|------|---------|-------|
| 持久化 | 内置 PersistentClient | 需手动序列化 |
| 元数据过滤 | 原生支持 | 需自己实现 |
| Python 友好度 | 高（纯 Python） | 中（需要编译） |
| 性能 | 够用（< 100K 文档） | 更好（> 1M 文档） |
| 已集成 | ✅ 已在项目中 | ❌ 需新增依赖 |

**结论**：ChromaDB 已经在项目中，且知识库规模小（< 10K 条目），ChromaDB 完全够用。

### 5.2 为什么选择 sentence-transformers 而不是 OpenAI Embedding

| 维度 | sentence-transformers | OpenAI Embedding |
|------|----------------------|------------------|
| 离线运行 | ✅ 完全本地 | ❌ 需要 API |
| 成本 | 免费 | $0.0001/1K tokens |
| 隐私 | 数据不出本机 | 数据发送到 OpenAI |
| 延迟 | ~10ms（本地） | ~100ms（网络） |
| 质量 | 够用（MTEB top 20%） | 更好（MTEB top 5%） |

**结论**：生物信息学场景下，数据隐私和离线可用性是硬需求。sentence-transformers 的质量对于我们的知识库规模（< 10K 条目）完全足够。

### 5.3 为什么分 3 个 Collection 而不是 1 个

1. **检索策略不同**：工具手册需要精确匹配工具名，领域知识需要语义检索，运行经验需要时间衰减
2. **独立更新**：工具手册很少变，运行经验频繁更新。分 Collection 可以独立重建索引
3. **top_k 不同**：工具手册 top_k=3 就够，领域知识可能需要 top_k=5
4. **元数据 schema 不同**：工具手册有 `tool_version`，运行经验有 `task_id`

### 5.4 为什么用 BM25 作为回退而不是 HashEmbedding

| 维度 | BM25 | HashEmbedding (当前) |
|------|------|---------------------|
| 语义能力 | 无（关键词匹配） | 无（字符 n-gram 匹配） |
| 检索质量 | 好（TF-IDF 变体，信息检索标准方法） | 差（哈希碰撞严重，维度稀疏） |
| 实现复杂度 | 低（jieba 分词 + 倒排索引） | 中（需要实现 ChromaDB 兼容接口） |
| 学术认可度 | 高（信息检索领域标准基线） | 无（非标准方法） |

**结论**：既然两者都没有语义能力，BM25 是更好的选择——它是信息检索领域的标准基线，面试官和审稿人都认可。

---

## 六、预期效果

### 6.1 定量目标

| 指标 | 当前值 | 目标值 | 测量方法 |
|------|--------|--------|----------|
| 知识库条目数 | 0 | 200+ | `collection.count()` |
| 检索 Hit Rate@5 | 0% | > 70% | 预构建评估集 |
| 检索 MRR | 0% | > 0.5 | 预构建评估集 |
| 错误诊断准确率 | 未测 | > 80% | 6 个诊断 case |
| Embedding 语义能力 | 无 | 有 | "OOM" 与 "内存不足" 可关联 |

### 6.2 论文价值

1. **RAG 增强的 Agent 决策**：可以展示 RAG 如何帮助 Agent 做出更准确的错误诊断和参数推荐
2. **消融实验**：有 RAG vs 无 RAG vs BM25 vs Hash Embedding 的对比，证明语义 RAG 的价值
3. **知识库构建方法论**：如何为特定生物信息学领域构建 RAG 知识库，这是方法论贡献

### 6.3 面试价值

1. 可以讲清楚 RAG 的完整链路：加载 → 分块 → 索引 → 检索 → 重排序 → 注入
2. 可以讲清楚 Embedding 选型的权衡：语义能力 vs 离线可用 vs 成本
3. 可以讲清楚多路召回 + RRF 融合的设计理由
4. 可以讲清楚评估体系的设计和消融实验的结果
