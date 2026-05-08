FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV CONDA_DIR=/opt/conda
ENV PATH="${CONDA_DIR}/bin:${PATH}"

RUN apt-get update && apt-get install -y \
    wget \
    curl \
    git \
    build-essential \
    python3-dev \
    python3-pip \
    libbz2-dev \
    liblzma-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

RUN wget -q https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O /tmp/miniconda.sh \
    && bash /tmp/miniconda.sh -b -p ${CONDA_DIR} \
    && rm /tmp/miniconda.sh \
    && conda init bash

RUN conda install -y -c bioconda \
    spades \
    flye \
    fastqc \
    blast \
    bwa \
    samtools \
    minimap2 \
    pilon \
    racon \
    medaka \
    getorganelle \
    mitoz \
    novoplasty \
    trnascan-se \
    hmmer \
    quast \
    && conda clean -afy

RUN pip install --no-cache-dir \
    biopython \
    pyyaml \
    click \
    rich \
    requests \
    pandas \
    numpy \
    matplotlib \
    langchain \
    chromadb \
    loguru \
    pydantic

WORKDIR /app

COPY . /app/mito-forge/

RUN cd /app/mito-forge && pip install -e .

ENV MITO_LANG=en
ENV MITO_CHROMA_DIR=/app/.mito-forge/chroma

ENTRYPOINT ["mito-forge"]
CMD ["--help"]
