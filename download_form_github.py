import os
import re
import json
import time
import py7zr
import rarfile
import zipfile
import urllib3
import logging
import fnmatch
import requests
import threading
from tqdm import tqdm

# 定义配置文件和日志文件的名称
CONFIG_FILENAME = "config.json"
LOG_FILENAME = "download_form_github.log"
GITHUB_API_BASE_URL = "https://api.github.com"
GITHUB_RAW_BASE_URL = "https://raw.githubusercontent.com"


def setup_logging(log_filename):
    """
    设置日志记录

    创建日志文件并设置日志格式。

    参数:
        log_filename (str): 日志文件的路径和名称。
    """
    # 检查日志文件是否存在，如果不存在则创建
    if not os.path.exists(log_filename):
        with open(log_filename, 'w', encoding='utf-8') as f:
            f.write("")

    # 设置日志格式
    console_formatter = logging.Formatter('%(message)s')
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

    # 设置控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)

    # 设置文件处理器
    file_handler = logging.FileHandler(log_filename, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(file_formatter)

    # 配置基本的日志记录设置
    logging.basicConfig(level=logging.INFO, handlers=[console_handler, file_handler])

    # 禁用不安全请求的警告
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def read_or_update_json_file(filename, data=None):
    """
    读取或更新 JSON 文件

    如果 data 为 None，读取 JSON 文件并返回数据；否则，将数据写入文件。

    参数:
        filename (str): JSON 文件的路径和名称。
        data (dict, optional): 要写入 JSON 文件的数据。默认为 None。

    返回:
        dict: 读取的 JSON 数据，如果发生错误则返回 None。
    """
    try:
        if data is None:
            # 读取 JSON 文件
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            # 写入数据到 JSON 文件
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logging.info(f"更新 JSON 文件: {filename}")
    except json.JSONDecodeError as e:
        logging.error(f"JSON 解码错误: {e}")
    except IOError as e:
        logging.error(f"文件 IO 错误: {e}")
    except Exception as e:
        logging.error(f"操作 JSON 文件时发生错误: {e}")
    return None


def prompt_user_selection(config):
    """
    获取用户输入以选择操作

    显示可用的操作并在 3 秒内未输入时执行默认操作。

    参数:
        config (dict): 配置数据。

    返回:
        str: 用户的选择。
    """

    def execute_default_action():
        """
        执行默认操作
        """
        nonlocal default_action_executed
        if not default_action_executed:
            default_action_executed = True
            github_token = config.get("github_token")
            print("=" * 100)
            process_projects(config, github_token)

    def get_user_input():
        """
        获取用户输入
        """
        nonlocal user_choice
        user_choice = input("请输入1、2 或 3 ，当输入其他时，将退出程序：\n")
        timer.cancel()

    print("请选择操作，3秒内未输入则执行默认操作：")
    print("-" * 100)
    print("1. 更新 Github Release 、下载 Github 文件（默认操作）")
    print("2. 修改“是否更新 Github Release”的标识")
    print("3. 修改“是否下载 Github 文件”的标识")
    print("-" * 100)

    user_choice = None
    default_action_executed = False

    # 定义一个计时器，在 3 秒后执行默认操作
    timer = threading.Timer(3.0, lambda: execute_default_action())
    # 创建并启动线程以获取用户输入
    input_thread = threading.Thread(target=get_user_input)
    input_thread.start()
    timer.start()
    input_thread.join()

    return user_choice


def process_projects(config, github_token):
    """
    处理项目的更新和下载操作

    参数:
        config (dict): 配置数据。
        github_token (str): GitHub API Token，用于身份验证。
    """
    logging.info("即将开始更新 Github 最新 Release")
    logging.info(f"{'-' * 100}")

    # 处理 Release 项目
    for project in config.get("release", []):
        if project.get("enabled"):
            owner = project.get("owner")
            repo = project.get("repository")
            save_path = os.path.expandvars(project.get("save_path"))
            version = project.get("version")
            stable_version = project.get("stable_version")
            extract_flag = project.get("extract_flag")
            files = project.get("files")

            logging.info(f"即将处理项目: {owner}/{repo}")
            download_releases_from_github(owner, repo, save_path, version, stable_version, extract_flag, files,
                                          github_token)
            logging.info(f"当前项目已处理完成: {owner}/{repo}")
            logging.info(f"{'-' * 100}")
        else:
            logging.info(f"项目 {project.get('owner')}/{project.get('repository')} 未启用下载, 将跳过下载")
            logging.info(f"{'-' * 100}")

    logging.info("Github 最新 Release 已更新完成")
    logging.info("=" * 100)

    # 处理文件项目
    logging.info("即将开始下载 Github 文件")
    logging.info(f"{'-' * 100}")

    for project in config.get("file", []):
        if project.get("enabled"):
            owner = project.get("owner")
            repo = project.get("repository")
            save_path = os.path.expandvars(project.get("save_path"))
            extract_flag = project.get("extract_flag")
            folder = project.get("folder")
            files = project.get("files")

            logging.info(f"即将处理项目: {owner}/{repo}")
            download_files_from_github(owner, repo, save_path, extract_flag, folder, files, github_token)
            logging.info(f"当前项目已处理完成: {owner}/{repo}")
            logging.info(f"{'-' * 100}")
        else:
            logging.info(f"项目 {project.get('owner')}/{project.get('repository')} 未启用下载, 将跳过下载")
            logging.info(f"{'-' * 100}")

    logging.info("Github 最新文件已下载完成")
    logging.info("=" * 100)


def send_http_request(url, token=None, stream=False):
    """
    发起 HTTP 请求，并返回响应

    如果提供了 token，添加到请求头中。

    参数:
        url (str): 要请求的 URL。
        token (str, optional): GitHub API Token，用于身份验证。默认为 None。
        stream (bool, optional): 是否以流的方式下载，默认为 False。

    返回:
        Response: 请求的响应对象，如果请求失败则返回 None。
    """
    retries = 3  # 最大重试次数，默认为 3
    backoff_factor = 1  # 重试间隔的乘数因子，默认为1
    headers = {'Authorization': f'token {token}'} if token else {}

    for attempt in range(retries):
        try:
            response = requests.get(url, headers=headers, verify=False, stream=stream)  # 发送请求
            response.raise_for_status()  # 检查请求是否成功
            return response
        except requests.HTTPError as http_err:
            logging.error(f"HTTP错误发生: {http_err} - URL: {url}")
        except requests.ConnectionError as conn_err:
            logging.error(f"连接错误发生: {conn_err} - URL: {url}")
        except requests.Timeout as timeout_err:
            logging.error(f"请求超时: {timeout_err} - URL: {url}")
        except requests.RequestException as e:
            logging.error(f"请求失败: {url}. 错误信息: {e}")

        # 如果发生错误，等待一段时间后重试
        wait_time = int(backoff_factor * (2 ** attempt))
        logging.info(f"等待 {wait_time} 秒后重试...")
        time.sleep(wait_time)

    return None


def download_releases_from_github(owner, repo, save_path, version, stable_version=True, extract_flag=True, files=None,
                                  token=None):
    """
    下载最新的 GitHub Release 文件并进行处理。

    该函数检查指定项目的 Release，比较本地版本与最新版本，
    如果需要更新，则下载最新的 Release 文件，并根据配置选项解压。

    参数:
        owner (str): GitHub 仓库的拥有者。
        repo (str): GitHub 仓库的名称。
        save_path (str): 下载文件保存的路径。
        version (str): 本地版本号，用于与最新版本进行比较。
        stable_version (bool, optional): 是否下载的稳定版本，默认为 True。
        extract_flag (bool, optional): 是否解压下载的文件，默认为 True。
        files (list, optional): 需要下载的特定文件名模式列表，默认为 None（下载所有文件）。
        token (str, optional): GitHub API Token，用于身份验证，默认为 None。

    返回:
        None: 如果成功处理了 Release 文件。
    """
    latest_url = f"{GITHUB_API_BASE_URL}/repos/{owner}/{repo}/releases/latest"
    releases_url = f"{GITHUB_API_BASE_URL}/repos/{owner}/{repo}/releases"

    def update_version_in_config(owner, repo, latest_version):
        """
        更新配置文件中的项目版本信息。

        Args:
            owner (str): 项目的拥有者。
            repo (str): 项目的名称。
            latest_version (str): 最新版本号。
        """
        data = read_or_update_json_file(CONFIG_FILENAME) or {}
        for project in data.get("release", []):
            if project.get("owner") == owner and project.get("repository") == repo:
                project["version"] = latest_version
        read_or_update_json_file(CONFIG_FILENAME, data)
        logging.info(f"项目 {owner}/{repo} 的版本号已更新为: {latest_version}")

    def handle_assets(assets):
        """
        处理下载的 Release 资产。

        根据提供的文件模式（如果有），下载匹配的资产。

        Args:
            assets (list): Release 中的资产列表。
        """
        if files:
            for asset in assets:
                for pattern in files:
                    if fnmatch.fnmatch(asset['name'], pattern):
                        file_url = asset['browser_download_url']
                        download_and_extract_file(file_url, asset['name'], save_path, extract_flag, token)
                        break
        else:
            for asset in assets:
                file_url = asset['browser_download_url']
                download_and_extract_file(file_url, asset['name'], save_path, extract_flag, token)

    try:
        # 判断版本号是否包含数字
        if not any(char.isdigit() for char in version):
            logging.info(f"项目 {owner}/{repo} 的版本号不包含数字，直接下载最新的 Release")
            latest_response = send_http_request(latest_url, token)
            latest_assets = latest_response.json().get('assets', [])
            handle_assets(latest_assets)
            return

        # 版本号包含数字，检查 stable_version
        if stable_version:
            logging.info(f"检查稳定版本: {owner}/{repo}")
            latest_response = send_http_request(latest_url, token)
            latest_data = latest_response.json()
            latest_release = latest_data.get('tag_name')

            if version == latest_release:
                logging.info(f"本地版本号与 GitHub 最新版本号一致，无需更新")
            else:
                logging.info(f"本地版本号落后于 GitHub 最新版本号，将下载最新的 Release")
                latest_assets = latest_data.get('assets', [])
                handle_assets(latest_assets)
                update_version_in_config(owner, repo, latest_release)

        else:
            logging.info(f"检查非稳定版本: {owner}/{repo}")
            releases_response = send_http_request(releases_url, token)
            releases = releases_response.json()
            if releases:
                release_0_version = releases[0].get('tag_name')

                if version == release_0_version:
                    logging.info(f"本地版本号与 GitHub release[0] 版本号一致，无需更新")
                else:
                    logging.info(f"本地版本号落后于 GitHub release[0] 版本号，将下载最新的 Release")
                    latest_assets = releases[0].get('assets', [])
                    handle_assets(latest_assets)
                    update_version_in_config(owner, repo, release_0_version)

    except Exception as e:
        logging.error(f"处理 Release 时发生错误: {e}")


def download_files_from_github(owner, repo, save_path, extract_flag=None, folder=None, files=None, token=None):
    """
    从 GitHub Raw 下载文件，保留文件夹结构，并覆盖已存在的文件

    根据提供的 owner 和 repo 下载指定文件或文件夹。

    参数:
        owner (str): GitHub 仓库的拥有者。
        repo (str): GitHub 仓库的名称。
        save_path (str): 下载文件保存的路径。
        extract_flag (bool, optional): 是否解压下载的文件，默认为 True。
        folder (str, optional): 指定的文件夹路径。默认为 None。
        files (list, optional): 要下载的文件名列表。默认为 None，表示下载所有文件。
        token (str, optional): GitHub API Token，用于身份验证。默认为 None。
    """

    def download_single_file(file_url, file_path):
        """
        从 URL 下载单个文件并覆盖已存在的文件

        参数:
            file_url (str): 文件的下载链接。
            file_path (str): 要保存的文件路径。
        """
        file_name = os.path.basename(file_path)
        file_dir = os.path.dirname(file_path)

        # 创建保存文件的目录
        if not os.path.exists(file_dir):
            os.makedirs(file_dir, exist_ok=True)

        # 下载文件并解压
        download_and_extract_file(file_url, file_name, file_dir, extract_flag, token)

    def fetch_files_in_directory(folder_url):
        """
        获取指定文件夹中的所有文件，以便进行通配符匹配

        参数:
            folder_url (str): 要获取文件夹内容的 URL。

        返回:
            list: 文件夹中的文件列表。
        """
        response = send_http_request(folder_url, token)
        if response is None:
            return []
        return response.json()

    def download_directory_contents(folder_url, folder_path, ignore_folder_structure):
        """
        递归下载文件夹中的所有文件和子文件夹

        参数:
            folder_url (str): 文件夹的 URL。
            folder_path (str): 保存文件的路径。
            ignore_folder_structure (bool): 是否忽略文件夹结构。
        """
        try:
            contents = fetch_files_in_directory(folder_url)  # 获取文件夹内容

            for item in contents:
                item_path = os.path.join(folder_path, item['name'])
                # 如果是文件，则下载
                if item['type'] == 'file':
                    file_url = item['download_url']
                    if files:
                        for file_pattern in files:
                            if fnmatch.fnmatch(item['name'], file_pattern):
                                download_single_file(file_url, item_path)  # 下载单个文件
                                break
                    else:
                        download_single_file(file_url, item_path)  # 下载单个文件
                # 如果是文件夹，则递归调用
                elif item['type'] == 'dir':
                    subfolder_url = f"{GITHUB_API_BASE_URL}/repos/{owner}/{repo}/contents/{item['path']}"
                    new_folder_path = item_path if not ignore_folder_structure else folder_path
                    download_directory_contents(subfolder_url, new_folder_path, ignore_folder_structure)  # 递归下载
        except Exception as e:
            logging.error(f"下载 GitHub 文件夹 {folder_path} 时发生错误: {e}")

    try:
        # 构造文件夹的 URL
        folder_url = (f"{GITHUB_API_BASE_URL}/repos/{owner}/{repo}/contents{folder}"
                      if folder
                      else f"{GITHUB_API_BASE_URL}/repos/{owner}/{repo}/contents")

        # 确定保存路径
        folder_path = os.path.normpath(save_path) if folder.startswith('/') else os.path.normpath(
            os.path.join(save_path, folder))
        os.makedirs(folder_path, exist_ok=True)

        # 开始下载目录内容
        download_directory_contents(folder_url, folder_path, folder.startswith('/'))

    except Exception as e:
        logging.error(f"下载 GitHub 文件时发生错误: {e}")


def download_and_extract_file(url, file_name, save_path, extract_flag, token=None):
    """
    从给定 URL 下载并解压文件

    下载文件后，如果是压缩文件则解压。

    参数:
        url (str): 文件的下载链接。
        save_path (str): 文件保存的路径。
        file_name (str): 下载后保存的文件名。
        token (str, optional): GitHub API Token，用于身份验证。默认为 None。

    返回:
        bool: 下载和解压是否成功。
    """
    save_path = os.path.abspath(save_path)
    file_save_path = os.path.join(save_path, file_name)
    older_version_file_path = os.path.join(save_path, f"[旧版本，将自动删除]{file_name}")

    def is_file_locked(file_path):
        """
        检查文件是否被锁定（使用中）

        参数:
            file_path (str): 要检查的文件路径。

        返回:
            bool: 文件是否被锁定。
        """
        try:
            with open(file_path, 'a'):
                return False  # 文件未被锁定
        except IOError:
            return True  # 文件被锁定

    def rename_file(old_file_path, new_file_path):
        """
        重命名文件

        参数:
            old_file_path (str): 旧文件的路径。
            new_file_path (str): 新文件的路径。
        """
        try:
            os.rename(old_file_path, new_file_path)
            logging.info(f"现有文件已重命名为: {new_file_path}")
        except Exception as e:
            logging.error(f"重命名文件时发生错误: {e}")

    def delete_old_file(file_path):
        """
        删除旧文件

        参数:
            file_path (str): 要删除的文件路径。
        """
        try:
            os.remove(file_path)
            logging.info(f"已删除旧版本文件: {file_path}")
        except Exception as e:
            logging.error(f"删除旧版本文件时发生错误: {e}")

    def download_file(url, save_path, file_name, token=None):
        """
        从给定 URL 下载文件

        返回下载的文件路径。

        参数:
            url (str): 文件的下载链接。
            save_path (str): 文件保存的路径。
            file_name (str): 下载后保存的文件名。
            token (str, optional): GitHub API Token，用于身份验证。默认为 None。

        返回:
            str: 下载的文件路径，如果下载失败则返回 None。
        """
        try:
            response = send_http_request(url, token, stream=True)  # 发送请求下载文件
            if response is None:
                return None

            total_size = int(response.headers.get('content-length', 0)) or 1  # 文件总大小
            os.makedirs(save_path, exist_ok=True)  # 创建保存路径

            file_save_path = os.path.join(save_path, file_name)
            # 以流式方式写入下载内容
            with open(file_save_path, 'wb') as f, tqdm(
                    desc=file_name,
                    total=total_size,
                    unit='B',
                    unit_scale=True,
                    unit_divisor=1024,
                    ncols=100,
                    ascii=True) as bar:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        bar.update(len(chunk))  # 更新进度条

            return file_save_path
        except Exception as e:
            logging.error(f"文件下载时发生错误: {e}")
            return None

    def extract_file(file_path, extract_path):
        """
        解压缩文件

        支持 ZIP、7Z 和 RAR 格式。

        参数:
            file_path (str): 要解压的文件路径。
            extract_path (str): 解压目标路径。

        返回:
            bool: 解压是否成功。
        """

        def extract_to_temp(file_path, temp_extract_path):
            if file_path.endswith('.zip'):
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_extract_path)  # 解压 ZIP 文件
                logging.info(f"已成功解压 ZIP 文件: {os.path.basename(file_path)}")
            elif file_path.endswith('.7z'):
                with py7zr.SevenZipFile(file_path, mode='r') as archive:
                    archive.extractall(path=temp_extract_path)  # 解压 7Z 文件
                logging.info(f"已成功解压 7Z 文件: {os.path.basename(file_path)}")
            elif file_path.endswith('.rar'):
                with rarfile.RarFile(file_path) as rar_ref:
                    rar_ref.extractall(temp_extract_path)  # 解压 RAR 文件
                logging.info(f"已成功解压 RAR 文件: {os.path.basename(file_path)}")
            else:
                logging.warning(f"不支持的压缩文件格式: {file_path}")
                return False
            return True

        def move_and_handle_conflict(src, dst):
            if os.path.exists(dst):
                if os.path.isdir(dst):
                    # 如果目标是目录，递归删除目录
                    import shutil
                    shutil.rmtree(dst)
                else:
                    os.remove(dst)
            os.rename(src, dst)

        try:
            temp_extract_path = os.path.join(extract_path, "temp_extract")
            os.makedirs(temp_extract_path, exist_ok=True)
            if not extract_to_temp(file_path, temp_extract_path):
                return False

            # 检查是否有一个顶层文件夹
            top_level_dirs = [name for name in os.listdir(temp_extract_path) if
                              os.path.isdir(os.path.join(temp_extract_path, name))]
            top_level_files = [name for name in os.listdir(temp_extract_path) if
                               os.path.isfile(os.path.join(temp_extract_path, name))]

            if len(top_level_dirs) == 1 and len(top_level_files) == 0:
                # 只有一个顶层文件夹
                top_level_dir = top_level_dirs[0]
                top_level_dir_path = os.path.join(temp_extract_path, top_level_dir)

                # 将顶层文件夹中的所有文件和文件夹移动到目标解压路径
                for item in os.listdir(top_level_dir_path):
                    s = os.path.join(top_level_dir_path, item)
                    d = os.path.join(extract_path, item)
                    move_and_handle_conflict(s, d)
            else:
                # 没有顶层文件夹，直接移动所有文件和文件夹到目标解压路径
                for item in os.listdir(temp_extract_path):
                    s = os.path.join(temp_extract_path, item)
                    d = os.path.join(extract_path, item)
                    move_and_handle_conflict(s, d)

            # 删除临时解压路径
            for item in os.listdir(temp_extract_path):
                item_path = os.path.join(temp_extract_path, item)
                if os.path.isdir(item_path):
                    os.rmdir(item_path)
                else:
                    os.remove(item_path)
            os.rmdir(temp_extract_path)

            return True
        except Exception as e:
            logging.error(f"解压文件时发生错误: {e}")
            return False

    try:
        logging.info(f"准备下载文件：{file_name} 到 {save_path}")
        logging.info(f"下载链接为: {url}")
        # 删除旧版本文件
        if os.path.isfile(older_version_file_path):
            delete_old_file(older_version_file_path)

        # 检查当前文件是否被占用
        if os.path.isfile(file_save_path):
            if is_file_locked(file_save_path):
                logging.warning(f"当前文件 {file_save_path} 被占用，尝试重命名为: [旧版本，将自动删除]{file_name}")
                rename_file(file_save_path, older_version_file_path)

        # 下载文件
        downloaded_file_path = download_file(url, save_path, file_name, token)
        if downloaded_file_path:
            # 如果下载的文件是压缩文件，则解压
            logging.info(f"文件成功下载到: {file_save_path}")
            if extract_flag:
                if downloaded_file_path.endswith(('.zip', '.7z', '.rar')):
                    if extract_file(downloaded_file_path, save_path):
                        os.remove(downloaded_file_path)  # 删除压缩文件
                        logging.info(f"已成功删除压缩文件: {file_name}")

        return True
    except Exception as e:
        logging.error(f"文件下载时发生错误: {e}")
        return False


def toggle_project_status(config, project_type):
    """
    显示项目列表，允许用户选择项目并切换其下载功能状态

    参数:
        config (dict): 配置数据。
        project_type (str): 项目的类型（如 "release" 或 "file"）。

    返回:
        dict: 更新后的配置数据。
    """
    projects = config.get(project_type, [])

    print(f"项目列表 - {project_type.capitalize()} 项目")
    print("-" * 100)

    # 输出项目列表及其状态
    for i, project in enumerate(projects):
        status_symbol = '√' if project['enabled'] else '×'
        print(
            f"{i + 1}. [{status_symbol}] {'已启用' if project['enabled'] else '未启用'}下载功能：{project['owner']}/{project['repository']}（{project.get('description', '')}）")

    print("-" * 100)
    user_input = input(
        "请选择需要启用或禁用下载功能的项目序号（可用空格、英文逗号、中文逗号、分号或斜杠中的任一分隔符分隔多个项目序号）：")
    print("-" * 100)

    # 解析用户输入的序号
    selected_indices = [int(i.strip()) - 1 for i in re.split(r'[，,；;/\s]+', user_input) if i.strip().isdigit()]

    invalid_indices = [i + 1 for i in selected_indices if i < 0 or i >= len(projects)]
    if invalid_indices:
        print(f"以下序号无效：{', '.join(map(str, invalid_indices))}")
        return config

    # 切换项目的启用状态
    for index in selected_indices:
        project = projects[index]
        new_status = "false" if project["enabled"] == "true" else "true"
        project["enabled"] = new_status
        logging.info(
            f"项目 {project['owner']}/{project['repository']} 的下载已{'启用' if new_status == 'true' else '禁用'}。")
        logging.info(f"{'-' * 100}")

    read_or_update_json_file(CONFIG_FILENAME, config)


def main():
    """
    主函数，执行下载任务或修改配置
    """
    setup_logging(LOG_FILENAME)  # 设置日志记录
    logging.info("=" * 100)

    # 读取配置文件
    config = read_or_update_json_file(CONFIG_FILENAME) or {}
    logging.info(f"已读取配置文件: {CONFIG_FILENAME}")
    logging.info("=" * 100)

    # 获取用户选择的操作
    user_choice = prompt_user_selection(config)

    if user_choice == '1':
        print("=" * 100)
        process_projects(config, config.get("github_token"))  # 处理项目下载

    elif user_choice == '2':
        print("=" * 100)
        toggle_project_status(config, "release")  # 切换 Release 项目的状态

    elif user_choice == '3':
        print("=" * 100)
        toggle_project_status(config, "file")  # 切换文件项目的状态

    else:
        logging.info("=" * 100)
        logging.info("无效的选择，将退出程序")
        logging.info("=" * 100)


if __name__ == "__main__":
    main()  # 执行主函数
