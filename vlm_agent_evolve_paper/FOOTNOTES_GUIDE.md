# 脚注符号说明

本模板支持以下作者脚注符号：

## 基础脚注

| 符号 | LaTeX 代码 | 说明 |
|------|-----------|------|
| `*` | `\textsuperscript{*}` | Work done during an internship at Alibaba |
| `†` | `\textsuperscript{\dag}` | Corresponding author |
| `‡` | `\textsuperscript{$\ddag$}` | Equal contribution (需配合 `\footnotetext`) |

## 使用示例

### 1. 基础配置（默认）

```latex
\author[1]{First Author\textsuperscript{*}}
\author[2]{Second Author\textsuperscript{\dag}}
\author[2]{Third Author}
\affil[1]{xxx University}
\affil[2]{Qwen Large Model Application Team, Alibaba}
\correspondingauthor{Second Author (\texttt{email@example.com})}
```

**效果：**
- First Author 带 `*` 脚注（实习说明）
- Second Author 带 `†` 脚注（通讯作者）
- 脚注显示：`*Work done during an internship at Alibaba. †Corresponding author.`

### 2. Equal Contribution（同等贡献）

```latex
\author[1]{First Author\textsuperscript{*,$\ddag$}}
\author[2]{Second Author\textsuperscript{$\ddag$,$\dag$}}
\author[2]{Third Author}
\affil[1]{xxx University}
\affil[2]{Qwen Large Model Application Team, Alibaba}

\footnotetext{\textsuperscript{$\ddag$}Equal contribution.}
\correspondingauthor{Second Author (\texttt{email@example.com})}
```

**效果：**
- First Author 和 Second Author 都带 `‡` 脚注（同等贡献）
- 脚注显示：`*Work done during an internship at Alibaba. †Corresponding author. ‡Equal contribution.`

### 3. 多个脚注组合

```latex
\author[1]{First Author\textsuperscript{*,$\ddag$}}  % 实习 + 同等贡献
\author[2]{Second Author\textsuperscript{$\ddag$,$\dag$}}  % 同等贡献 + 通讯作者
```

**注意：** 多个脚注用逗号分隔，放在同一个 `\textsuperscript{}` 中。

## 自定义脚注

如需添加其他自定义脚注，可以使用：

```latex
\footnotetext{\textsuperscript{§}Custom footnote text.}
```

然后在作者名后添加 `§` 符号：

```latex
\author[1]{Author Name\textsuperscript{§}}
```
