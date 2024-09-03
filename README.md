# 从 GitHub 更新 Release 或下载文件

## 简介

该项目旨在简化从 GitHub 下载最新版本 Release 和特定文件的过程。用户可以通过简单的配置文件来设置需要下载的项目，程序将自动处理下载和更新逻辑。

## 目录

- [使用方法](#使用方法)
- [操作说明](#操作说明)
- [项目文件描述](#项目文件描述)
- [配置文件说明](#配置文件说明)
- [处理 release 项目逻辑说明](#处理-release-项目逻辑说明)
- [处理 file 项目逻辑说明](#处理-file-项目逻辑说明)
- [函数及其作用](#函数及其作用)

## 使用方法

1. 下载本项目最新 Release 中的压缩包。
2. 解压后，确保 `config.json` 配置文件正确设置。
3. 双击 `download_form_github.exe` 启动程序。
4. 在提示输入选择时，输入 `1`、`2` 或 `3` 执行相应操作。若 3 秒内未输入，则程序将执行默认操作（更新 GitHub Release、下载
   GitHub 文件）。

---

## 操作说明

- **操作 1**：更新 GitHub Release 、下载 GitHub 文件（默认操作）
- **操作 2**：修改“是否更新 GitHub Release”的标识
- **操作 3**：修改“是否下载 GitHub 文件”的标识

### 操作 1：更新 Release

更新最新 Release 或下载文件。

### 操作 2：修改 Release 状态

- 读取 `config.json` 中的 `release`。
- 将 `release` 整合成一个有序号的列表。
- 根据输入的序号列表改变是否下载的标识。

### 操作 3：修改文件状态

- 读取 `config.json` 中的 `file`。
- 将 `file` 整合成一个有序号的列表。
- 根据输入的序号列表改变是否下载的标识。

---

## 项目文件描述

- **download_form_github.py**：主要执行文件
- **config.json**：用于配置下载内容和设置

---

## 配置文件说明

- `config.json` 中的内容可以自定义，但需注意`json`格式。
- `config.json` 包括 3 种信息，分别是 `github_token`、`release`、`file`。

### `config.json`格式如下

```json
{
  "github_token": "请填写你自己的 Github Token，自行搜索获取方式",
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

### `github_token`说明

- 默认为空，可自行设置自己的 `github_token`
- 它用于下载文件时，避免访问 GitHub API 时达到请求限制。
- 如果为空，下载时不携带 GitHub Token。
- 如果不为空，下载时携带 GitHub Token。

### `release`和`file`中的参数说明如下所示

| 参数            | 说明                           |
|---------------|------------------------------|
| `enabled`     | 是否启用下载                       |
| `owner`       | 仓库所有者                        |
| `repository`  | 仓库名称                         |
| `version`     | 版本                           |
| `description` | 该项目在 Github 中的描述             |
| `github_url`  | GitHub 的 URL 地址（仅供参考，暂无实际作用） |
| `save_path`   | 保存到本地的路径                     |
| `folder`      | 需要下载的文件夹及文件夹下的文件（注意 / 的使用）   |
| `files`       | 需要下载的文件（可为空，支持通配符）           |

---

## 处理 release 项目逻辑说明

- 更新 Release 时，将 `config.json` 中的版本信息与 GitHub API 中的最新版进行比较。
- 若有更新的版本，会下载最新 Release，并同步更新 `config.json` 的 version。
- 如果版本号不包含数字，会直接下载最新的Release，并同步更新 `config.json` 的 version。
- 如果没有 Release，则下载 最新的Artifact`的全部文件。

---

## 处理 file 项目逻辑说明

- 下载文件时，目前不会记录和比较文件最后更新时间。
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

## 函数及其作用

| 函数名称                       | 作用                        |
|----------------------------|---------------------------|
| `setup_logging`            | 设置日志记录                    |
| `read_or_update_json_file` | 读取或更新 JSON 文件             |
| `get_user_choice`          | 获取用户输入以选择操作               |
| `process_projects`         | 处理项目的更新和下载操作              |
| `make_request`             | 发起 HTTP 请求并返回响应           |
| `process_github_release`   | 下载最新的 GitHub 的 Release 文件 |
| `process_github_artifact`  | 下载 GitHub 的 Artifact 文件   |
| `process_github_file`      | 从 GitHub 下载文件，覆盖已存在的文件    |
| `download_and_unzip`       | 从给定 URL 下载并解压文件           |
| `modify_project_status`    | 显示项目列表，允许用户选择项目并切换其下载功能状态 |
| `main`                     | 主函数，执行下载任务或修改配置           |