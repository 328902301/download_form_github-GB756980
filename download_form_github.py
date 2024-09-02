import re  # 导入用于正则表达式操作的模块
import os  # 导入用于文件和目录操作的模块
import json  # 导入用于处理 JSON 数据的模块
import py7zr  # 导入用于处理 7z 文件的模块
import rarfile  # 导入用于处理 RAR 文件的模块
import zipfile  # 导入用于处理 ZIP 文件的模块
import urllib3  # 导入用于处理 HTTP 请求的模块
import logging  # 导入用于记录日志的模块
import requests  # 导入用于发送 HTTP 请求的模块
import fnmatch  # 导入用于文件名匹配的模块
import threading  # 导入用于线程操作的模块
from tqdm import tqdm  # 导入用于显示进度条的模块

# 定义配置文件和日志文件的名称
CONFIG_FILE = "config.json"  # 配置文件路径
LOG_FILE = "download_log.txt"  # 日志文件路径

# 定义 GitHub API 和 Raw URL 的全局变量
GITHUB_API_URL = "https://api.github.com"  # GitHub API 基础 URL
GITHUB_RAW_URL = "https://raw.githubusercontent.com"  # GitHub Raw 文件 URL


def setup_logging(log_file):
    """设置日志记录
    创建日志文件并设置日志格式。

    参数:
        log_file (str): 日志文件的路径和名称。
    """
    # 如果日志文件不存在，则创建一个空文件
    if not os.path.exists(log_file):
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write("")  # 写入空内容

    # 设置控制台输出的格式
    console_formatter = logging.Formatter('%(message)s')
    # 设置文件输出的格式
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s',
                                       datefmt='%Y-%m-%d %H:%M:%S')  # 添加时间戳

    # 创建文件处理器，写入日志到文件
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)  # 设置日志级别为 INFO
    file_handler.setFormatter(file_formatter)  # 设置文件格式

    # 创建控制台处理器，输出日志到控制台
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)  # 设置日志级别为 INFO
    console_handler.setFormatter(console_formatter)  # 设置控制台格式

    # 配置日志记录，设置日志级别和处理器
    logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler])
    # 禁用 HTTPS 警告
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def read_or_update_json_file(file_name, data=None):
    """读取或更新 JSON 文件
    如果 data 为 None，读取 JSON 文件并返回数据；否则，将数据写入文件。

    参数:
        file_name (str): JSON 文件的路径和名称。
        data (dict, optional): 要写入 JSON 文件的数据。默认为 None。

    返回:
        dict: 读取的 JSON 数据，如果发生错误则返回 None。
    """
    try:
        if data is None:  # 如果没有数据，读取 JSON 文件
            with open(file_name, 'r', encoding='utf-8') as f:  # 打开文件以读取
                return json.load(f)  # 返回 JSON 数据
        else:  # 如果有数据，更新 JSON 文件
            with open(file_name, 'w', encoding='utf-8') as f:  # 打开文件以写入
                json.dump(data, f, indent=4, ensure_ascii=False)  # 写入 JSON 数据
            logging.info(f"更新 JSON 文件: {file_name}")  # 记录更新日志
    except json.JSONDecodeError as e:  # 捕捉 JSON 解码错误
        logging.error(f"JSON 解码错误: {e}")  # 记录错误日志
    except IOError as e:  # 捕捉文件 IO 错误
        logging.error(f"文件 IO 错误: {e}")  # 记录错误日志
    except Exception as e:  # 捕捉其他异常
        logging.error(f"操作 JSON 文件时发生错误: {e}")  # 记录错误日志
    return None  # 返回 None


def make_request(url, token=None, stream=False):
    """发起 HTTP 请求，并返回响应
    如果提供了 token，添加到请求头中。

    参数:
        url (str): 要请求的 URL。
        token (str, optional): GitHub API Token，用于身份验证。默认为 None。
        stream (bool, optional): 是否以流的方式下载，默认为 False。

    返回:
        Response: 请求的响应对象，如果请求失败则返回 None。
    """
    # 设置请求头，如果提供了 token，则添加到请求头中
    headers = {'Authorization': f'token {token}'} if token else {}

    try:
        # 发送 GET 请求
        response = requests.get(url, headers=headers, verify=False, stream=stream)
        response.raise_for_status()  # 检查响应状态码
        return response  # 返回响应对象
    except requests.HTTPError as http_err:  # 捕捉 HTTP 错误
        logging.error(f"HTTP错误发生: {http_err} - URL: {url}")  # 记录错误日志
    except requests.ConnectionError as conn_err:  # 捕捉连接错误
        logging.error(f"连接错误发生: {conn_err} - URL: {url}")  # 记录错误日志
    except requests.Timeout as timeout_err:  # 捕捉超时错误
        logging.error(f"请求超时: {timeout_err} - URL: {url}")  # 记录错误日志
    except requests.RequestException as e:  # 捕捉请求异常
        logging.error(f"请求失败: {url}. 错误信息: {e}")  # 记录错误日志
    return None  # 返回 None


def download_and_unzip(url, save_path, file_name, token=None):
    """从给定 URL 下载并解压文件
    下载文件后，如果是压缩文件则解压。

    参数:
        url (str): 文件的下载链接。
        save_path (str): 文件保存的路径。
        file_name (str): 下载后保存的文件名。
        token (str, optional): GitHub API Token，用于身份验证。默认为 None。

    返回:
        bool: 下载和解压是否成功。
    """
    save_path = os.path.abspath(save_path)  # 获取文件保存路径的绝对路径
    file_save_path = os.path.join(save_path, file_name)  # 拼接文件保存路径
    older_version_file_path = os.path.join(save_path, f"【旧版本, 请手动删除】{file_name}")  # 旧版本文件路径

    logging.info(f"准备下载文件：{file_name} 到 {save_path}")  # 记录准备下载日志
    logging.info(f"下载链接为: {url}")  # 记录下载链接

    def is_file_locked(file_path):
        """检查文件是否被锁定（使用中）
        尝试以追加模式打开文件，若失败则说明被锁定。

        参数:
            file_path (str): 要检查的文件路径。

        返回:
            bool: 文件是否被锁定。
        """
        try:
            with open(file_path, 'a'):  # 尝试以追加模式打开文件
                return False  # 文件未被锁定
        except IOError:  # 捕捉 IO 错误
            return True  # 文件被锁定

    def download_file(url, save_path, file_name, token=None):
        """从给定 URL 下载文件
        下载完成后返回下载的文件路径。

        参数:
            url (str): 文件的下载链接。
            save_path (str): 文件保存的路径。
            file_name (str): 下载后保存的文件名。
            token (str, optional): GitHub API Token，用于身份验证。默认为 None。

        返回:
            str: 下载的文件路径，如果下载失败则返回 None。
        """
        try:
            response = make_request(url, token, stream=True)  # 发起请求，使用流的方式
            if response is None:
                return None  # 返回 None

            total_size = int(response.headers.get('content-length', 0)) or 1  # 获取文件总大小
            os.makedirs(save_path, exist_ok=True)  # 创建保存路径
            file_save_path = os.path.join(save_path, file_name)  # 拼接文件保存路径

            # 以二进制写入方式打开文件并显示下载进度条
            with open(file_save_path, 'wb') as f, tqdm(
                    desc=file_name,  # 设置进度条描述
                    total=total_size,  # 设置总大小
                    unit='B',  # 设置单位为字节
                    unit_scale=True,  # 自动缩放单位
                    unit_divisor=1024,  # 单位转换
                    ncols=100,  # 进度条宽度
                    ascii=True) as bar:  # 使用 ASCII 字符
                for chunk in response.iter_content(chunk_size=8192):  # 使用较大的块大小
                    if chunk:  # 如果块不为空
                        f.write(chunk)  # 写入文件
                        bar.update(len(chunk))  # 更新进度条

            logging.info(f"文件成功下载到: {save_path}")  # 记录成功下载日志
            return file_save_path  # 返回文件保存路径
        except Exception as e:  # 捕捉其他异常
            logging.error(f"文件下载时发生错误: {e}")  # 记录错误日志
            return None  # 返回 None

    def extract_file(file_path, extract_path):
        """解压缩文件
        支持 ZIP、7Z 和 RAR 格式。

        参数:
            file_path (str): 要解压的文件路径。
            extract_path (str): 解压目标路径。

        返回:
            bool: 解压是否成功。
        """
        try:
            if file_path.endswith('.zip'):  # 如果是 ZIP 文件
                with zipfile.ZipFile(file_path, 'r') as zip_ref:  # 打开 ZIP 文件
                    zip_ref.extractall(extract_path)  # 解压到指定路径
                logging.info(f"已成功解压 ZIP 文件: {file_name}")  # 记录解压成功日志
            elif file_path.endswith('.7z'):  # 如果是 7Z 文件
                with py7zr.SevenZipFile(file_path, mode='r') as archive:  # 打开 7Z 文件
                    archive.extractall(path=extract_path)  # 解压到指定路径
                logging.info(f"已成功解压 7Z 文件: {file_name}")  # 记录解压成功日志
            elif file_path.endswith('.rar'):  # 如果是 RAR 文件
                with rarfile.RarFile(file_path) as rar_ref:  # 打开 RAR 文件
                    rar_ref.extractall(extract_path)  # 解压到指定路径
                logging.info(f"已成功解压 RAR 文件: {file_name}")  # 记录解压成功日志
            else:  # 如果文件格式不支持
                logging.warning(f"不支持的压缩文件格式: {file_name}")  # 记录警告日志
                return False  # 返回失败
            return True  # 返回成功
        except Exception as e:  # 捕捉其他异常
            logging.error(f"解压文件时发生错误: {e}")  # 记录错误日志
            return False  # 返回失败

    try:
        if os.path.isfile(file_save_path):  # 如果文件已存在
            if is_file_locked(file_save_path):  # 检查文件是否被锁定
                logging.warning(f"{file_name} 已被占用, 尝试重命名为: 【旧版本, 请手动删除】{file_name}")  # 记录警告
                try:
                    os.rename(file_save_path, older_version_file_path)  # 尝试重命名文件
                    logging.info(f"现有文件已重命名为: {older_version_file_path}")  # 记录重命名成功日志
                except PermissionError:  # 捕捉权限错误
                    logging.error(f"无法重命名文件: {file_name}, 文件可能正在被占用")  # 记录错误日志
                    return False  # 返回失败
                except Exception as e:  # 捕捉其他异常
                    logging.error(f"重命名文件时发生错误: {e}")  # 记录错误日志
                    return False  # 返回失败
            else:  # 如果文件未被占用
                logging.info(f"{file_name} 已存在, 但未被占用, 将直接下载并覆盖原文件")  # 记录信息日志

        # 下载文件
        downloaded_file_path = download_file(url, save_path, file_name, token)  # 下载文件
        if downloaded_file_path:  # 检查下载文件路径
            # 检查文件扩展名并解压
            if downloaded_file_path.endswith(('.zip', '.7z', '.rar')):  # 如果是压缩文件
                if extract_file(downloaded_file_path, save_path):  # 解压文件
                    # 删除压缩文件
                    os.remove(downloaded_file_path)  # 删除压缩文件
                    logging.info(f"已成功删除压缩文件: {file_name}")  # 记录删除日志

        return True  # 返回成功
    except Exception as e:  # 捕捉其他异常
        logging.error(f"文件下载时发生错误: {e}")  # 记录错误日志
        return False  # 返回失败


def download_github_release(owner, repo, version, save_path, files=None, token=None):
    """下载最新的 GitHub Release 文件
    根据提供的 owner 和 repo 下载最新的 Release 文件。

    参数:
        owner (str): GitHub 仓库的拥有者。
        repo (str): GitHub 仓库的名称。
        version (str): 要检查的版本号。
        save_path (str): 下载文件保存的路径。
        files (list, optional): 要下载的文件名列表。默认为 None，表示下载所有文件。
        token (str, optional): GitHub API Token，用于身份验证。默认为 None。

    返回:
        None
    """
    url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/releases/latest"  # 构建获取最新 Release 的 URL

    def update_version_in_config(owner, repo, latest_version):
        """更新 config.json 中指定项目的版本号

        参数:
            owner (str): GitHub 仓库的拥有者。
            repo (str): GitHub 仓库的名称。
            latest_version (str): 最新的版本号。

        返回:
            None
        """
        data = read_or_update_json_file(CONFIG_FILE) or {}  # 读取配置文件
        for project in data.get("release", []):  # 遍历 Release 项目
            if project.get("owner") == owner and project.get("repository") == repo:  # 匹配项目
                project["version"] = latest_version  # 更新版本号
        read_or_update_json_file(CONFIG_FILE, data)  # 更新配置文件
        logging.info(f"项目 {owner}/{repo} 的版本号已更新为: {latest_version}")  # 记录更新日志

    try:
        response = make_request(url, token)  # 发起请求获取 Release 信息
        if response is None:  # 检查响应
            return  # 返回

        release = response.json()  # 获取 JSON 格式的 Release 信息
        latest_version = release.get('tag_name', 'unknown')  # 获取最新版本号

        if re.search(r'\d', version) is None:  # 如果版本号不包含数字
            logging.info(f"项目 {owner}/{repo} 的版本号不包含数字, 将优先下载最新 Release")  # 记录信息日志
            assets = release.get('assets', [])  # 获取 Release 的资产
            if assets:  # 检查资产
                for asset in assets:  # 遍历资产
                    file_name = asset['name']  # 获取文件名
                    file_url = asset['browser_download_url']  # 获取下载链接
                    download_and_unzip(file_url, save_path, file_name, token)  # 下载并解压
            else:  # 如果没有可用的 Release
                logging.info(f"项目 {owner}/{repo} 没有可用的 Release, 尝试下载最新的 Artifact")  # 记录信息日志
                download_github_artifact(owner, repo, save_path, token=token)  # 下载最新 Artifact

            update_version_in_config(owner, repo, latest_version)  # 更新版本号

        elif version != latest_version:  # 如果版本号不相同
            assets = release.get('assets', [])  # 获取资产
            files_to_download = [asset['name'] for asset in assets] if not files else files  # 获取需要下载的文件

            for asset in assets:  # 遍历资产
                file_name = asset['name']  # 获取文件名
                if any(fnmatch.fnmatch(file_name, pattern) for pattern in files_to_download):  # 匹配文件
                    file_url = asset['browser_download_url']  # 获取下载链接
                    download_and_unzip(file_url, save_path, file_name, token)  # 下载并解压

            update_version_in_config(owner, repo, latest_version)  # 更新版本号

        else:  # 如果版本号相同
            logging.info(f"项目 {owner}/{repo} 本地版本为 {version}, 已是最新, 将跳过下载")  # 记录信息日志

    except Exception as e:  # 捕捉其他异常
        logging.error(f"处理 Release 时发生错误: {e}")  # 记录错误日志


def download_github_artifact(owner, repo, save_path, token=None):
    """下载 GitHub 的 Artifact 文件
    根据提供的 owner 和 repo 下载最新的 Artifact 文件。

    参数:
        owner (str): GitHub 仓库的拥有者。
        repo (str): GitHub 仓库的名称。
        save_path (str): 下载文件保存的路径。
        token (str, optional): GitHub API Token，用于身份验证。默认为 None。

    返回:
        None
    """
    url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/actions/artifacts"  # 构建获取 Artifact 的 URL

    try:
        response = make_request(url, token)  # 发起请求获取 Artifact 信息
        if response is None:  # 检查响应
            return  # 返回

        artifacts = response.json().get('artifacts', [])  # 获取 Artifact 列表
        if artifacts:  # 检查是否有 Artifact
            latest_artifact = artifacts[0]  # 获取最新 Artifact
            artifact_url = latest_artifact['archive_download_url']  # 获取下载链接
            artifact_name = f"{latest_artifact['name']}.zip"  # 构建文件名

            download_and_unzip(artifact_url, save_path, artifact_name, token)  # 下载并解压
        else:  # 如果没有找到 Artifact
            logging.info("未找到 Artifact 文件。")  # 记录信息日志
    except Exception as e:  # 捕捉其他异常
        logging.error(f"处理 Github Artifact 时, 发生错误: {e}")  # 记录错误日志


def download_github_file(owner, repo, save_path, folder=None, files=None, token=None):
    """从 GitHub Raw 下载文件，保留文件夹结构，并覆盖已存在的文件
    根据提供的 owner 和 repo 下载指定文件或文件夹。

    参数:
        owner (str): GitHub 仓库的拥有者。
        repo (str): GitHub 仓库的名称。
        save_path (str): 下载文件保存的路径。
        folder (str, optional): 指定的文件夹路径。默认为 None。
        files (list, optional): 要下载的文件名列表。默认为 None，表示下载所有文件。
        token (str, optional): GitHub API Token，用于身份验证。默认为 None。

    返回:
        None
    """

    def download_from_url(file_url, file_path):
        """从 URL 下载单个文件并覆盖已存在的文件

        参数:
            file_url (str): 文件的下载链接。
            file_path (str): 要保存的文件路径。

        返回:
            None
        """
        file_name = os.path.basename(file_path)  # 获取文件名
        file_dir = os.path.dirname(file_path)  # 获取文件目录

        if not os.path.exists(file_dir):  # 如果目录不存在
            os.makedirs(file_dir, exist_ok=True)  # 创建目录

        download_and_unzip(file_url, file_dir, file_name, token)  # 下载并解压

    def fetch_files_in_folder(folder_url):
        """获取指定文件夹中的所有文件，以便进行通配符匹配

        参数:
            folder_url (str): 要获取文件夹内容的 URL。

        返回:
            list: 文件夹中的文件列表。
        """
        response = make_request(folder_url, token)  # 发起请求
        if response is None:  # 检查响应
            return []  # 返回空列表
        return response.json()  # 返回文件夹内容

    def download_folder_contents(folder_url, folder_path, ignore_folder_structure):
        """递归下载文件夹中的所有文件和子文件夹

        参数:
            folder_url (str): 文件夹的 URL。
            folder_path (str): 保存文件的路径。
            ignore_folder_structure (bool): 是否忽略文件夹结构。

        返回:
            None
        """
        try:
            contents = fetch_files_in_folder(folder_url)  # 获取文件夹内容

            for item in contents:  # 遍历内容
                item_path = os.path.join(folder_path, item['name'])  # 获取文件路径
                if item['type'] == 'file':  # 如果是文件
                    file_url = item['download_url']  # 获取下载链接
                    if files:  # 如果指定了文件
                        for file_pattern in files:  # 遍历文件模式
                            if fnmatch.fnmatch(item['name'], file_pattern):  # 匹配文件名
                                download_from_url(file_url, item_path)  # 下载文件
                                break  # 跳出循环
                    else:  # 如果没有指定文件
                        download_from_url(file_url, item_path)  # 下载文件
                elif item['type'] == 'dir':  # 如果是文件夹
                    subfolder_url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/contents/{item['path']}"  # 获取子文件夹 URL
                    new_folder_path = item_path if not ignore_folder_structure else folder_path  # 确定新文件夹路径
                    download_folder_contents(subfolder_url, new_folder_path, ignore_folder_structure)  # 递归下载子文件夹
        except Exception as e:  # 捕捉其他异常
            logging.error(f"下载 GitHub 文件夹 {folder_path} 时发生错误: {e}")  # 记录错误日志

    try:
        # 统一处理逻辑
        folder_url = (f"{GITHUB_API_URL}/repos/{owner}/{repo}/contents{folder}"
                      if folder
                      else f"{GITHUB_API_URL}/repos/{owner}/{repo}/contents")  # 获取文件夹 URL

        folder_path = os.path.normpath(save_path) if folder.startswith('/') else os.path.normpath(
            os.path.join(save_path, folder))  # 获取文件夹路径
        os.makedirs(folder_path, exist_ok=True)  # 创建文件夹

        # 下载文件夹内容
        download_folder_contents(folder_url, folder_path, folder.startswith('/'))  # 递归下载文件夹内容

    except Exception as e:  # 捕捉其他异常
        logging.error(f"下载 GitHub 文件时发生错误: {e}")  # 记录错误日志


def modify_project_status(config, project_type):
    """显示项目列表，允许用户选择项目并切换其下载功能状态

    参数:
        config (dict): 配置文件的内容。
        project_type (str): 项目的类型（如 "release" 或 "file"）。

    返回:
        dict: 更新后的配置文件内容。
    """
    projects = config.get(project_type, [])  # 获取指定项目类型的项目列表

    print(f"项目列表 - {project_type.capitalize()} 项目")  # 打印项目列表标题
    print("-" * 100)  # 打印分隔线
    for i, project in enumerate(projects):  # 遍历项目列表
        status_symbol = '√' if project['enabled'] == "true" else '×'  # 根据状态设置符号
        print(
            f"{i + 1}. [{status_symbol}] {'已启用' if project['enabled'] == 'true' else '未启用'}下载功能：{project['owner']}/{project['repository']}（{project.get('description', '')}）")  # 打印项目信息

    print("-" * 100)  # 打印分隔线
    user_input = input(
        "请选择需要启用或禁用下载功能的项目序号（可用空格、英文逗号、中文逗号、分号或斜杠中的任一分隔符分隔多个项目序号）：")  # 获取用户输入
    print("-" * 100)  # 打印分隔线

    # 处理用户输入，提取所选项目的索引
    selected_indices = [int(i.strip()) - 1 for i in re.split(r'[，,；;/\s]+', user_input) if
                        i.strip().isdigit()]  # 提取有效的项目序号

    # 检查无效的序号
    invalid_indices = [i + 1 for i in selected_indices if i < 0 or i >= len(projects)]  # 找出无效序号
    if invalid_indices:  # 如果有无效序号
        print(f"以下序号无效：{', '.join(map(str, invalid_indices))}")  # 打印无效序号
        return config  # 返回配置

    # 切换选定项目的状态
    for index in selected_indices:  # 遍历选定的索引
        project = projects[index]  # 获取项目
        new_status = "false" if project["enabled"] == "true" else "true"  # 切换状态
        project["enabled"] = new_status  # 更新状态
        logging.info(
            f"项目 {project['owner']}/{project['repository']} 的下载已{'启用' if new_status == 'true' else '禁用'}。")  # 记录更新日志
        logging.info(f"{'-' * 100}")  # 打印分隔线

    read_or_update_json_file(CONFIG_FILE, config)  # 更新配置文件


def main():
    """主函数，执行下载任务或修改配置

    返回:
        None
    """
    setup_logging(LOG_FILE)  # 设置日志记录
    logging.info(f"{'=' * 100}")  # 打印分隔线
    config = read_or_update_json_file(CONFIG_FILE) or {}  # 读取配置文件
    logging.info(f"已读取配置文件: {CONFIG_FILE}")  # 记录读取日志
    logging.info(f"{'=' * 100}")  # 打印分隔线

    print("请选择操作，3秒内未输入则执行默认操作：")  # 提示用户选择操作
    print("-" * 100)  # 打印分隔线
    print("1. 更新 Github Release 、下载 Github 文件（默认操作）")  # 操作选项
    print("2. 修改“是否更新 Github Release”的标识")  # 操作选项
    print("3. 修改“是否下载 Github 文件”的标识")  # 操作选项
    print("-" * 100)  # 打印分隔线

    choice = None  # 初始化用户选择
    default_action_executed = False  # 初始化默认操作执行状态

    timer = threading.Timer(3.0, lambda: (exec_default_action()))  # 设置 3 秒计时器

    def exec_default_action():
        """执行默认操作

        返回:
            None
        """
        print("=" * 100)  # 打印分隔线
        nonlocal default_action_executed  # 使用外部变量
        if not default_action_executed:  # 如果默认操作未执行
            default_action_executed = True  # 标记为已执行
            github_token = config.get("github_token")  # 获取 GitHub Token

            if github_token:  # 如果 Token 存在
                logging.info("已从 config.json 中加载 GitHub Token")  # 记录加载 Token 日志
                logging.info(f"{'=' * 100}")  # 打印分隔线
            else:  # 如果 Token 不存在
                logging.warning("未在 config.json 中配置 GitHub Token, 下载时将不携带 GitHub Token")  # 记录警告日志
                logging.info(f"{'=' * 100}")  # 打印分隔线

            logging.info("即将开始更新 Github 最新 Release")  # 记录信息日志
            logging.info(f"{'-' * 100}")  # 打印分隔线
            for project in config.get("release", []):  # 遍历 Release 项目
                if project.get("enabled") == "true":  # 如果项目已启用
                    owner = project.get("owner")  # 获取 owner
                    repo = project.get("repository")  # 获取 repo
                    version = project.get("version")  # 获取版本号
                    save_path = os.path.expandvars(project.get("save_path"))  # 解析保存路径
                    files = project.get("files")  # 获取文件列表
                    logging.info(f"即将处理项目: {owner}/{repo}")  # 记录处理项目日志
                    download_github_release(owner, repo, version, save_path, files, github_token)  # 下载 Release
                    logging.info(f"当前项目已处理完成: {owner}/{repo}")  # 记录处理完成日志
                    logging.info(f"{'-' * 100}")  # 打印分隔线
                else:  # 如果项目未启用
                    logging.info(
                        f"项目 {project.get('owner')}/{project.get('repository')} 未启用下载, 将跳过下载")  # 记录跳过日志
                    logging.info(f"{'-' * 100}")  # 打印分隔线
            logging.info("Github 最新 Release 已更新完成")  # 记录更新完成日志
            logging.info(f"{'=' * 100}")  # 打印分隔线

            logging.info("即将开始下载 Github 文件")  # 记录信息日志
            logging.info(f"{'-' * 100}")  # 打印分隔线
            for project in config.get("file", []):  # 遍历文件项目
                if project.get("enabled") == "true":  # 如果项目已启用
                    owner = project.get("owner")  # 获取 owner
                    repo = project.get("repository")  # 获取 repo
                    save_path = os.path.expandvars(project.get("save_path"))  # 解析保存路径
                    folder = project.get("folder")  # 获取文件夹
                    files = project.get("files")  # 获取文件列表

                    logging.info(f"即将处理项目: {owner}/{repo}")  # 记录处理项目日志
                    download_github_file(owner, repo, save_path, folder, files, github_token)  # 下载文件
                    logging.info(f"当前项目已处理完成: {owner}/{repo}")  # 记录处理完成日志
                    logging.info(f"{'-' * 100}")  # 打印分隔线
                else:  # 如果项目未启用
                    logging.info(
                        f"项目 {project.get('owner')}/{project.get('repository')} 未启用下载, 将跳过下载")  # 记录跳过日志
                    logging.info(f"{'-' * 100}")  # 打印分隔线
            logging.info("Github 最新文件已下载完成")  # 记录下载完成日志
            logging.info(f"{'=' * 100}")  # 打印分隔线

    def get_user_input():
        """获取用户输入以选择操作

        返回:
            None
        """
        nonlocal choice  # 使用外部变量
        choice = input("请输入1、2 或 3 ，当输入其他时，将退出程序：\n")  # 获取用户输入
        timer.cancel()  # 取消计时器

    input_thread = threading.Thread(target=get_user_input)  # 创建获取用户输入的线程
    input_thread.start()  # 启动线程

    timer.start()  # 启动计时器

    input_thread.join()  # 等待线程结束

    if choice == '1':  # 如果用户选择 1
        exec_default_action()  # 执行默认操作

    elif choice == '2':  # 如果用户选择 2
        print("=" * 100)  # 打印分隔线
        modify_project_status(config, "release")  # 修改 Release 项目的状态
        logging.info("=" * 100)  # 打印分隔线

    elif choice == '3':  # 如果用户选择 3
        print("=" * 100)  # 打印分隔线
        modify_project_status(config, "file")  # 修改文件项目的状态
        logging.info("=" * 100)  # 打印分隔线

    else:  # 如果用户输入无效
        logging.info("=" * 100)  # 打印分隔线
        logging.info("无效的选择，将退出程序")  # 记录无效选择日志
        logging.info("=" * 100)  # 打印分隔线


if __name__ == "__main__":
    main()  # 执行主函数