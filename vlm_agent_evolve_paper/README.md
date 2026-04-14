# QABG Paper Template

基于会议论文格式清理后的 LaTeX 模板，支持单栏/双栏切换。

## 📝 单栏/双栏切换

在 `main.tex` 文件顶部（第7-10行），注释/取消注释对应行即可：

```latex
% 单栏布局（撰写编辑推荐）
\documentclass[10pt, a4paper, logo]{googledeepmind}
% 双栏布局（会议投稿推荐）
% \documentclass[10pt, a4paper, twocolumn, logo]{googledeepmind}
```

**切换后记得清除缓存重新编译：**
```bash
rm -f *.aux *.log *.out *.bbl *.blg
pdflatex main.tex
```

## 📚 Demo 文件

- `demo_singlecolumn.pdf` - 单栏布局示例
- `demo_twocolumn.pdf` - 双栏布局示例

## 🚀 快速开始

```bash
# 编译
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex

# 查看
open main.pdf  # macOS
# 或 xdg-open main.pdf  # Linux
```

## 📂 文件结构

```
├── main.tex                  # 主文件（可切换单栏/双栏）
├── demo_singlecolumn.pdf     # 单栏示例
├── demo_twocolumn.pdf        # 双栏示例
├── googledeepmind.cls        # 文档类
├── conference.bib/bst        # 参考文献
├── math_commands.tex         # 数学命令
├── figures/                  # 图片文件夹
└── README.md                 # 本文件
```

## ✏️ 常用操作

### 修改标题作者
```latex
\title{Your Paper Title}
\author[1]{First Author\textsuperscript{*}}      % * 实习脚注
\author[2]{Second Author\textsuperscript{\dag}} % † 通讯作者
\affil[1]{xxx University}
\affil[2]{Qwen Large Model Application Team, Alibaba}
\correspondingauthor{Second Author (\texttt{email@example.com})}
```

**脚注说明：**
- `\textsuperscript{*}` - 实习脚注："Work done during an internship at Alibaba"
- `\textsuperscript{\dag}` - 通讯作者脚注
- `\textsuperscript{$\ddag$}` - 同等贡献脚注（需添加 `\footnotetext{\textsuperscript{$\ddag$}Equal contribution.}`）

**Equal Contribution 示例：**
```latex
\author[1]{First Author\textsuperscript{*,$\ddag$}}
\author[2]{Second Author\textsuperscript{$\ddag$,$\dag$}}
\footnotetext{\textsuperscript{$\ddag$}Equal contribution.}
```

### 插入图片
```latex
\begin{figure}[htbp]
\centering
\includegraphics[width=0.8\columnwidth]{figures/your_image.pdf}
\caption{Figure caption}
\label{fig:label}
\end{figure}
```

### 创建表格
```latex
\begin{table}[htbp]
\centering
\caption{Table caption}
\begin{tabular}{lcc}
\toprule
Method & Metric 1 & Metric 2 \\
\midrule
Baseline & 85.2 & 78.3 \\
Ours & \best{92.3} & \best{86.7} \\
\bottomrule
\end{tabular}
\end{table}
```

## 💡 自定义命令

- `\best{text}` - 最佳结果（绿色+粗体）
- `\secondbest{text}` - 次佳结果（黄色背景）
- `\rr{text}` - 红色文本
- `\bb{text}` - 蓝色文本

## ⚠️ 注意事项

1. 单栏→双栏切换时，图片宽度建议从 `\textwidth` 改为 `\columnwidth`
2. 宽表格在双栏模式下可使用 `table*` 环境跨栏
3. 切换布局后需清除缓存重新编译

## 📖 原始来源

基于论文 "Eliminating Inductive Bias in Reward Models with Information-Theoretic Guidance" 清理而成。
