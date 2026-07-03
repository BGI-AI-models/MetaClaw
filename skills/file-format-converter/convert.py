#!/usr/bin/env python3
"""
file-format-converter/convert.py
宏基因组学文件格式转换入口
Brain 通过命令行调用：python convert.py --input X --output-format Y [options]
"""

import argparse
import hashlib
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ── 日志配置 ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("converter")


# ── 格式自动检测 ──────────────────────────────────────────────────────────────
EXTENSION_MAP = {
    ".fastq": "fastq", ".fq": "fastq",
    ".fastq.gz": "fastq", ".fq.gz": "fastq",
    ".fasta": "fasta", ".fa": "fasta", ".fna": "fasta",
    ".fasta.gz": "fasta", ".fa.gz": "fasta",
    ".bam": "bam",
    ".sam": "sam",
    ".cram": "cram",
    ".biom": "biom",
    ".tsv": "tsv", ".txt": "tsv",
    ".json": "json",
    ".csv": "csv",
}

def detect_format(path: Path) -> str:
    name = path.name.lower()
    # 先匹配双扩展名
    for ext, fmt in EXTENSION_MAP.items():
        if name.endswith(ext):
            return fmt
    raise ValueError(
        f"无法自动检测格式：{path.name}，请通过 --input-format 手动指定"
    )


# ── MD5 校验 ──────────────────────────────────────────────────────────────────
def md5(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


# ── 行数统计（序列文件用 seqkit，表格用 wc）────────────────────────────────
def count_records(path: Path, fmt: str) -> str:
    try:
        if fmt in ("fastq", "fasta"):
            result = subprocess.run(
                ["seqkit", "stats", "-T", str(path)],
                capture_output=True, text=True, timeout=120
            )
            lines = result.stdout.strip().splitlines()
            if len(lines) >= 2:
                cols = lines[1].split("\t")
                return f"{cols[3]} 条序列" if len(cols) > 3 else "统计失败"
        else:
            result = subprocess.run(
                ["wc", "-l", str(path)],
                capture_output=True, text=True, timeout=30
            )
            n = int(result.stdout.split()[0])
            return f"{n} 行"
    except Exception as e:
        return f"统计失败（{e}）"
    return "未知"


# ── 写转换日志 ────────────────────────────────────────────────────────────────
def write_log(log_path: Path, meta: dict):
    with open(log_path, "w") as f:
        f.write("# 文件格式转换日志\n")
        f.write(f"时间：{meta['timestamp']}\n\n")
        f.write(f"## 输入\n")
        f.write(f"- 路径：{meta['input']}\n")
        f.write(f"- 格式：{meta['input_fmt']}\n")
        f.write(f"- MD5：{meta['input_md5']}\n")
        f.write(f"- 记录数：{meta['input_records']}\n\n")
        f.write(f"## 输出\n")
        f.write(f"- 路径：{meta['output']}\n")
        f.write(f"- 格式：{meta['output_fmt']}\n")
        f.write(f"- MD5：{meta['output_md5']}\n")
        f.write(f"- 记录数：{meta['output_records']}\n\n")
        f.write(f"## 执行命令\n")
        f.write(f"```bash\n{meta['command']}\n```\n")
    log.info(f"转换日志已写入：{log_path}")


# ── 转换路由 ──────────────────────────────────────────────────────────────────
def run(cmd: list[str], desc: str):
    log.info(f"执行：{' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log.error(f"{desc} 失败：\n{result.stderr}")
        sys.exit(result.returncode)
    return " ".join(cmd)


def convert_fastq_to_fasta(src: Path, dst: Path, compress: bool) -> str:
    out = str(dst) + (".gz" if compress else "")
    return run(
        ["seqkit", "fq2fa", str(src), "-o", out],
        "FASTQ → FASTA"
    )


def convert_fasta_to_fastq(src: Path, dst: Path, compress: bool) -> str:
    # FASTA 没有质量值，用假质量填充（I = Phred40）
    out = str(dst) + (".gz" if compress else "")
    return run(
        ["seqkit", "convert", "--from", "fasta", "--to", "fastq",
         "-o", out, str(src)],
        "FASTA → FASTQ"
    )


def convert_bam_to_fastq(src: Path, dst: Path, r2: Path | None, threads: int) -> str:
    if r2:
        cmd = [
            "samtools", "collate", "-O", "-u", str(src), "|",
            "samtools", "fastq",
            "-1", str(dst),
            "-2", str(r2),
            "-0", "/dev/null",
            "-s", "/dev/null",
            "-n", "-F", "0x900",
            "-@", str(threads),
        ]
        # shell=True 用于管道
        full_cmd = " ".join(cmd)
        log.info(f"执行（shell）：{full_cmd}")
        result = subprocess.run(full_cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            log.error(f"BAM → FASTQ 失败：{result.stderr}")
            sys.exit(1)
        return full_cmd
    else:
        return run(
            ["samtools", "fastq", "-@", str(threads),
             "-0", str(dst), str(src)],
            "BAM → FASTQ（interleaved）"
        )


def convert_sam_bam(src: Path, dst: Path, threads: int) -> str:
    in_fmt = detect_format(src)
    if in_fmt == "sam":
        return run(
            ["samtools", "view", "-bS", "-@", str(threads),
             "-o", str(dst), str(src)],
            "SAM → BAM"
        )
    else:
        return run(
            ["samtools", "view", "-h", "-@", str(threads),
             "-o", str(dst), str(src)],
            "BAM → SAM"
        )


def convert_biom_to_tsv(src: Path, dst: Path) -> str:
    return run(
        ["biom", "convert", "-i", str(src),
         "-o", str(dst), "--to-tsv"],
        "BIOM → TSV"
    )


def convert_tsv_to_biom(src: Path, dst: Path) -> str:
    return run(
        ["biom", "convert", "-i", str(src),
         "-o", str(dst),
         "--table-type=OTU table",
         "--to-hdf5"],
        "TSV → BIOM"
    )


def convert_biom_to_json(src: Path, dst: Path) -> str:
    return run(
        ["biom", "convert", "-i", str(src),
         "-o", str(dst), "--to-json"],
        "BIOM → JSON"
    )


def convert_tsv_wide_to_long(src: Path, dst: Path) -> str:
    """宽格式（samples × features）转长格式（tidy），用 pandas 实现"""
    try:
        import pandas as pd
    except ImportError:
        log.error("缺少 pandas，请在 brain 容器中安装：pip install pandas")
        sys.exit(1)

    df = pd.read_csv(src, sep="\t", index_col=0)
    long_df = df.reset_index().melt(
        id_vars=df.index.name or "feature",
        var_name="sample",
        value_name="abundance"
    )
    long_df.to_csv(dst, sep="\t", index=False)
    return f"pandas melt: {src} → {dst}"


def compress_file(src: Path, dst: Path, threads: int) -> str:
    return run(
        ["pigz", "-p", str(threads), "-c", str(src)],
        "gzip 压缩"
    )


def decompress_file(src: Path, dst: Path) -> str:
    return run(["pigz", "-d", "-c", str(src)], "gzip 解压")


# ── 主函数 ────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="宏基因组学文件格式转换工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python convert.py --input sample.fastq.gz --output-format fasta
  python convert.py --input reads.bam --output-format fastq --paired-r2 reads_R2.fastq
  python convert.py --input abundance.biom --output-format tsv
  python convert.py --input table.tsv --output-format tsv-long
        """
    )
    parser.add_argument("--input", required=True, help="输入文件路径")
    parser.add_argument("--input-format", help="输入格式（可自动检测）")
    parser.add_argument("--output-format", required=True,
                        choices=["fastq", "fasta", "bam", "sam",
                                 "biom", "tsv", "tsv-long", "json", "gz"],
                        help="目标格式")
    parser.add_argument("--output-file", help="输出文件路径（默认自动命名）")
    parser.add_argument("--paired-r2", help="BAM→FASTQ 时的 R2 输出路径")
    parser.add_argument("--threads", type=int, default=4, help="线程数（默认 4）")
    parser.add_argument("--compress", action="store_true", help="输出 gzip 压缩")
    args = parser.parse_args()

    src = Path(args.input).resolve()
    if not src.exists():
        log.error(f"输入文件不存在：{src}")
        sys.exit(1)

    # 检测输入格式
    in_fmt = args.input_format or detect_format(src)
    out_fmt = args.output_format

    # 确定输出路径
    if args.output_file:
        dst = Path(args.output_file).resolve()
    else:
        suffix_map = {
            "fastq": ".fastq", "fasta": ".fasta",
            "bam": ".bam", "sam": ".sam",
            "biom": ".biom", "tsv": ".tsv",
            "tsv-long": "_long.tsv", "json": ".json",
            "gz": ".gz",
        }
        stem = src.name.replace(".gz", "").rsplit(".", 1)[0]
        dst = src.parent / f"{stem}_converted{suffix_map[out_fmt]}"

    dst.parent.mkdir(parents=True, exist_ok=True)
    log_path = dst.parent / f"{dst.name}.convert.log"

    log.info(f"输入：{src}（{in_fmt}）")
    log.info(f"输出：{dst}（{out_fmt}）")

    # 记录转换前信息
    input_md5 = md5(src)
    input_records = count_records(src, in_fmt)

    # ── 路由到对应转换函数 ──
    cmd_record = ""
    key = (in_fmt, out_fmt)

    if key == ("fastq", "fasta"):
        cmd_record = convert_fastq_to_fasta(src, dst, args.compress)
    elif key == ("fasta", "fastq"):
        cmd_record = convert_fasta_to_fastq(src, dst, args.compress)
    elif key in [("bam", "fastq"), ("bam", "fasta")]:
        r2 = Path(args.paired_r2).resolve() if args.paired_r2 else None
        cmd_record = convert_bam_to_fastq(src, dst, r2, args.threads)
    elif key in [("sam", "bam"), ("bam", "sam")]:
        cmd_record = convert_sam_bam(src, dst, args.threads)
    elif key == ("biom", "tsv"):
        cmd_record = convert_biom_to_tsv(src, dst)
    elif key == ("biom", "json"):
        cmd_record = convert_biom_to_json(src, dst)
    elif key == ("tsv", "biom"):
        cmd_record = convert_tsv_to_biom(src, dst)
    elif key == ("tsv", "tsv-long") or out_fmt == "tsv-long":
        cmd_record = convert_tsv_wide_to_long(src, dst)
    elif out_fmt == "gz":
        cmd_record = compress_file(src, dst, args.threads)
    elif in_fmt == "gz":
        cmd_record = decompress_file(src, dst)
    else:
        log.error(f"不支持的转换路径：{in_fmt} → {out_fmt}")
        log.error("支持的路径请参阅 SKILL.md")
        sys.exit(1)

    if not dst.exists():
        log.error(f"转换失败：输出文件未生成（{dst}）")
        sys.exit(1)

    # 记录转换后信息并写日志
    write_log(log_path, {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "input": str(src),
        "input_fmt": in_fmt,
        "input_md5": input_md5,
        "input_records": input_records,
        "output": str(dst),
        "output_fmt": out_fmt,
        "output_md5": md5(dst),
        "output_records": count_records(dst, out_fmt),
        "command": cmd_record,
    })

    log.info(f"转换完成：{dst}")


if __name__ == "__main__":
    main()
