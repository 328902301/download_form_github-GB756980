# 从 GitHub 更新 Release 或下载文件

## 简介

该项目整合了以下两个项目：

- [download_github_release（下载 Github 最新 Release）](https://github.com/GB756980/download_github_release)
- [download_github_file（下载 Github 文件）](https://github.com/GB756980/download_github_file)

## 使用方法

1. 下载本项目最新 Release 中的压缩包。
2. 解压后，双击 `download_form_github.exe`。
3. 打开后，会提示输入 1、2 或 3 执行相应的操作。
4. 若 3 秒内未输入，则执行默认操作（更新 Github Release 、下载 Github 文件）。

---

## 操作说明

- **操作 1**：更新 Github Release 、下载 Github 文件（默认操作）
- **操作 2**：修改“是否更新 Github Release”的标识
- **操作 3**：修改“是否下载 Github 文件”的标识

### 操作 1

更新最新 Release 或下载文件。

### 操作 2

- 读取 `config.json` 中的 Release。
- 将 Release 整合成一个有序号的列表。
- 根据输入的序号列表改变是否下载的标识。
- 显示效果为 `[√]已启用下载功能：owner/repository（description）`。

### 操作 3

- 读取 `config.json` 中的 File。
- 将 File 整合成一个有序号的列表。
- 根据输入的序号列表改变是否下载的标识。
- 显示效果为 `[√]已启用下载功能：owner/repository（description）`。

---

## 项目文件描述

- 项目有两个文件，分别是 `config.json` 和 `download_form_github.py`。
- Release 的压缩包中包含 `config.json` 和 `download_form_github.exe`。

### config.json 格式如下：

```json
{
  "github_token": "",
  "release": [
    {
      "enabled": "true",
      "owner": "notepad-plus-plus",
      "repository": "notepad-plus-plus",
      "description": "Notepad++ 是一个免费的源代码编辑器和记事本替代品，支持多种编程语言和自然语言。",
      "github_url": "https://github.com/2dust/v2rayN",
      "version": "v8.6.9",
      "save_path": "D:\\Program\\Editor&IDE\\Notepad++",
      "files": [
        "npp.*.portable.x64.7z"
      ]
    }
  ],
  "file": [
    {
      "enabled": "true",
      "owner": "sch-lda",
      "repository": "yctest2",
      "description": "YimMenu的广告黑名单文件。",
      "github_url": "https://github.com/sch-lda/yctest2/tree/main/Lua",
      "save_path": "%APPDATA%\\YimMenu\\",
      "folder": "",
      "files": [
        "ad.json",
        "ad_rid.json"
      ]
    }
  ]
}
```

- 下载最新 Release 中的全部文件或下载文件夹下的全部文件：`"files": []`
- 指定需要下载的文件名称：`"files": ["A", "B"]`

---

## 项目详细说明

`config.json` 包括 3 种信息，目前有 `github_token`、`release`、`file`。

- **github_token** 默认为空，可自行设置自己的 `github_token`，用于下载文件时，避免访问 GitHub API 时达到请求限制。
    - 如果为空，下载时将不携带 GitHub Token；如果不为空，则携带。

### release 和 file 中的参数如下所示：

| 参数            | 说明                      |
|---------------|-------------------------|
| `enabled`     | 是否启用下载                  |
| `owner`       | 仓库所有者                   |
| `repository`  | 仓库名称                    |
| `version`     | 版本                      |
| `description` | 该项目的描述                  |
| `github_url`  | GitHub 的地址（仅供参考，暂无实际作用） |
| `save_path`   | 保存到本地的路径                |
| `folder`      | 需要下载的文件夹及文件夹下的文件        |
| `files`       | 需要下载的文件夹（支持通配符）         |

---

## 更新`release`逻辑

- 更新 release 时，将 `config.json` 中的版本信息与 GitHub API 中的最新版进行比较。
- 若有更新的版本，会下载`最新 Release`，并同步更新 `config.json` 的 version。
- 如果版本号不包含数字，会直接下载`最新 Release`，并同步更新 `config.json` 的 version。
- 如果没有`Release`，则下载`最新 Artifact`的全部文件。

---

## 下载 `file` 逻辑

- 下载 `file` 时，目前不会进行文件更新时间的记录和比较。
- 如果 `folder` 为空，`files` 不为空，则下载仓库根目录的 `files` 文件。
- 如果 `folder` 不为空（例如 `"folder": "/Lua"`），`files` 不为空，则下载 `folder` 下的 `files` 文件，不保留当前 folder 结构。
- 如果 `folder` 不为空（例如 `"folder": "Lua"`），`files` 不为空，则下载 `folder` 下的 `files` 文件，并保留当前 folder 结构。
- 如果 `folder` 不为空（例如 `"folder": "/Lua"`），`files` 为空，则下载 `folder` 下的全部文件（包括子文件夹），不保留当前
  `folder`结构，但保留子文件夹结构。
- 如果 `folder` 不为空（例如 `"folder": "Lua"`），`files` 为空，则下载 `folder` 下的全部文件（包括子文件夹），并保留当前
  `folder` `结构和子文件夹结构。

- 对于 `"folder": "/Lua"`， `folder` 仅用来帮助拼接下载链接，不在 `save_path` 中体现。

- 对于 `"folder": "Lua"`， `folder` 在 `save_path` 中体现。

---

## `download_form_github.py` 中的函数及其作用

| 函数名称                       | 作用                   |
|----------------------------|----------------------|
| `setup_logging`            | 设置日志输出               |
| `read_or_update_json_file` | 读写 JSON 文件           |
| `make_request`             | 发送请求                 |
| `download_and_unzip`       | 下载并解压文件              |
| `download_github_release`  | 下载 GitHub 的 release  |
| `download_github_artifact` | 下载 GitHub 的 artifact |
| `download_github_file`     | 下载 GitHub 的 file     |
| `modify_project_status`    | 修改是否下载的标识            |
| `main`                     | 主函数                  |