# 从 Github更新 Release 或下载文件


## 简介
该项目整合了以下两个项目：
- [download_github_release（下载 Github 最新 Release）](https://github.com/GB756980/download_github_release)

- [download_github_file（下载 Github 文件）](https://github.com/GB756980/download_github_file)

## 使用方法
````
下载最新 Release 中的压缩包。
解压后，双击 download_form_github.exe 。
打开后，会提示 输入1、2 或 3执行相应的操作。
若3秒内未输入，则执行默认操作（更新  Github Release 、下载 Github 文件）
````

````
操作1：更新  Github Release 、下载 Github 文件（默认操作）
操作2：修改“是否更新  Github Release”的标识"
操作3：修改“是否下载 Github 文件”的标识"
````

````
操作1：会更新 Release 或下载文件
````

````
操作2：
读取 config.json 中的 release
将 release 整合成一个有序号的列表
每个项目都有序号，根据输入的序号列表来改变是否下载的标识
显示效果为  [√]已启用下载功能：owner/repository（description）
如果原本为false，则该为true；如果原本为true，则改为false
````

````
操作3：
读取json中的Release。
将 file 整合成一个有序号的列表
每个项目都有序号，根据输入的序号列表来改变是否下载的标识
显示效果为  [√]已启用下载功能：owner/repository（description）
如果原本为false，则该为true；如果原本为true，则改为false
````

## 项目文件描述
````
项目有两个文件，分别是 config.json 和 download_form_github.py
Release的压缩包中有 config.json 和 download_form_github.exe
````
config.json格式如下：
```plaintext
{
  "github_token": "",
  "release": [
    {
      "enabled": "true",
      "owner": "2dust",
      "repository": "v2rayN",
      "description": "适用于 Windows 的 GUI 客户端，支持 Xray Core 和 v2fly Core 等。",
      "github_url": "https://github.com/2dust/v2rayN",
      "version": "6.55",
      "save_path": "D:\\加速",
      "files": [
        "v2rayN.zip"
      ]
    }
  ],
  "file": [
    {
      "enabled": "true",
      "owner": "sch-lda",
      "repository": "yctest2",
      "description": "此翻译方式为劫持翻译，将Lua传入Yimmenu的显示相关API的参数进行实时替换。",
      "github_url": "https://github.com/sch-lda/yctest2/tree/main/Lua",
      "save_path": "%APPDATA%\\YimMenu\\translations",
      "folder": "Lua",
      "files": [
        "lua_lang.json"
      ]
    }
  ]
}
```

````
下载最新 Release 中的全部文件 或者 下载文件夹下的全部文件："files": []
指定需要下载的文件名称："files": ["A","B"]
````

## 项目详细说明
````
config.json 包括 3 种信息，目前有 github_token 、 release 、 file 。
````

````
github_token 默认为空，可自行设置自己的 github_token。
它用于下载文件时，避免访问 GitHub API 时达到请求限制。
如果为空，下载时将不携带 GitHub Token。如果不为空，则携带。

release 和 file 中的 key 如下所示：
enabled：是否启用下载
owner：仓库所有者
repository：仓库名称
version：版本
description：该项目的描述
github_url：github的地址（仅供参考，代码中暂时没用到）
save_path：保存到本地的路径
folder：需要下载的文件夹及文件夹下的文件
files：需要下载的文件夹
````

````
更新release时，将 config.json 中的版本信息与 api.github 中的最新版进行比较。

若有更新的版本，就会下载最新的release，并同步更新config.json的version。

如果版本号为CI，则下载最新release，且跳过版本检测、不更新version。如果没有release，则下载最新工件的全部文件。
````

````
下载file时，目前不会进行文件更新时间的记录和比较。

如果“需要下载的文件夹”为空，则下载仓库根目录的“需要下载的文件”文件。

如果“需要下载的文件夹”不为空，“需要下载的文件”不为空，则下载“需要下载的文件夹”下的“需要下载的文件”文件。

如果“需要下载的文件夹”不为空，“需要下载的文件”为空，则下载“需要下载的文件夹”文件夹下的全部文件（不包括子文件夹）。
````

````
download_form_github.py 代码中的函数及其作用如下：
download_and_unzip 下载解压文件
download_github_release 下载github的release
download_github_artifact  下载github的artifact
download_github_file 下载github的file
read_or_update_json_file 读写json文件
modify_project_status 修改是否下载的标识
main 主函数
````
