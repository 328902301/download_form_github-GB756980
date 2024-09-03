import re
import os
import json
import py7zr
import rarfile
import zipfile
import urllib3
import logging
import requests
import fnmatch
import threading
from tqdm import tqdm

# 定义配置文件和日志文件的名称
CONFIG_FILE = "config.json"
LOG_FILE = "download_log.txt"
GITHUB_API_URL = "https://api.github.com"
GITHUB_RAW_URL = "https://raw.githubusercontent.com"


def setup_logging(log_file):
    """设置日志记录

    创建日志文件并设置日志格式。

    参数:
        log_file (str): 日志文件的路径和名称。
    """
    if not os.path.exists(log_file):
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write("")

    console_formatter = logging.Formatter('%(message)s')
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(file_formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)

    logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler])
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
        if data is None:
            with open(file_name, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            with open(file_name, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            logging.info(f"更新 JSON 文件: {file_name}")
    except json.JSONDecodeError as e:
        logging.error(f"JSON 解码错误: {e}")
    except IOError as e:
        logging.error(f"文件 IO 错误: {e}")
    except Exception as e:
        logging.error(f"操作 JSON 文件时发生错误: {e}")
    return None


def get_user_choice(config):
    """获取用户输入以选择操作

    显示可用的操作并在 3 秒内未输入时执行默认操作。

    参数:
        config (dict): 配置数据。

    返回:
        str: 用户的选择。
    """
    print("请选择操作，3秒内未输入则执行默认操作：")
    print("-" * 100)
    print("1. 更新 Github Release 、下载 Github 文件（默认操作）")
    print("2. 修改“是否更新 Github Release”的标识")
    print("3. 修改“是否下载 Github 文件”的标识")
    print("-" * 100)

    choice = None
    default_action_executed = False

    timer = threading.Timer(3.0, lambda: exec_default_action())

    def exec_default_action():
        """执行默认操作"""
        nonlocal default_action_executed
        if not default_action_executed:
            default_action_executed = True
            github_token = config.get("github_token")
            print("=" * 100)
            process_projects(config, github_token)

    def get_user_input():
        """获取用户输入"""
        nonlocal choice
        choice = input("请输入1、2 或 3 ，当输入其他时，将退出程序：\n")
        timer.cancel()

    input_thread = threading.Thread(target=get_user_input)
    input_thread.start()
    timer.start()
    input_thread.join()

    return choice


def process_projects(config, github_token):
    """处理项目的更新和下载操作

    参数:
        config (dict): 配置数据。
        github_token (str): GitHub API Token，用于身份验证。
    """
    logging.info("即将开始更新 Github 最新 Release")
    logging.info(f"{'-' * 100}")

    # 处理 Release 项目
    for project in config.get("release", []):
        if project.get("enabled") == "true":
            owner = project.get("owner")
            repo = project.get("repository")
            version = project.get("version")
            save_path = os.path.expandvars(project.get("save_path"))
            files = project.get("files")

            logging.info(f"即将处理项目: {owner}/{repo}")
            process_github_release(owner, repo, version, save_path, files, github_token)
            logging.info(f"当前项目已处理完成: {owner}/{repo}")
            logging.info(f"{'-' * 100}")
        else:
            logging.info(f"项目 {project.get('owner')}/{project.get('repository')} 未启用下载, 将跳过下载")
            logging.info(f"{'-' * 100}")

    logging.info("Github 最新 Release 已更新完成")
    logging.info(f"{'=' * 100}")

    # 处理文件项目
    logging.info("即将开始下载 Github 文件")
    logging.info(f"{'-' * 100}")

    for project in config.get("file", []):
        if project.get("enabled") == "true":
            owner = project.get("owner")
            repo = project.get("repository")
            save_path = os.path.expandvars(project.get("save_path"))
            folder = project.get("folder")
            files = project.get("files")

            logging.info(f"即将处理项目: {owner}/{repo}")
            process_github_file(owner, repo, save_path, folder, files, github_token)
            logging.info(f"当前项目已处理完成: {owner}/{repo}")
            logging.info(f"{'-' * 100}")
        else:
            logging.info(f"项目 {project.get('owner')}/{project.get('repository')} 未启用下载, 将跳过下载")
            logging.info(f"{'-' * 100}")

    logging.info("Github 最新文件已下载完成")


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
    headers = {'Authorization': f'token {token}'} if token else {}

    try:
        response = requests.get(url, headers=headers, verify=False, stream=stream)
        response.raise_for_status()
        return response
    except requests.HTTPError as http_err:
        logging.error(f"HTTP错误发生: {http_err} - URL: {url}")
    except requests.ConnectionError as conn_err:
        logging.error(f"连接错误发生: {conn_err} - URL: {url}")
    except requests.Timeout as timeout_err:
        logging.error(f"请求超时: {timeout_err} - URL: {url}")
    except requests.RequestException as e:
        logging.error(f"请求失败: {url}. 错误信息: {e}")
    return None


def process_github_release(owner, repo, version, save_path, files=None, token=None):
    """下载最新的 GitHub Release 文件

    根据提供的 owner 和 repo 下载最新的 Release 文件。

    参数:
        owner (str): GitHub 仓库的拥有者。
        repo (str): GitHub 仓库的名称。
        version (str): 要检查的版本号。
        save_path (str): 下载文件保存的路径。
        files (list, optional): 要下载的文件名列表。默认为 None，表示下载所有文件。
        token (str, optional): GitHub API Token，用于身份验证。默认为 None。
    """
    url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/releases/latest"

    def update_version_in_config(owner, repo, latest_version):
        """更新 config.json 中指定项目的版本号

        参数:
            owner (str): GitHub 仓库的拥有者。
            repo (str): GitHub 仓库的名称。
            latest_version (str): 最新的版本号。
        """
        data = read_or_update_json_file(CONFIG_FILE) or {}
        for project in data.get("release", []):
            if project.get("owner") == owner and project.get("repository") == repo:
                project["version"] = latest_version
        read_or_update_json_file(CONFIG_FILE, data)
        logging.info(f"项目 {owner}/{repo} 的版本号已更新为: {latest_version}")

    try:
        response = make_request(url, token)
        if response is None:
            return

        release = response.json()
        latest_version = release.get('tag_name', 'unknown')

        if re.search(r'\d', version) is None:
            logging.info(f"项目 {owner}/{repo} 的版本号不包含数字, 将优先下载最新 Release")
            assets = release.get('assets', [])
            if assets:
                for asset in assets:
                    file_name = asset['name']
                    file_url = asset['browser_download_url']
                    download_and_unzip(file_url, save_path, file_name, token)
            else:
                logging.info(f"项目 {owner}/{repo} 没有可用的 Release, 尝试下载最新的 Artifact")
                process_github_artifact(owner, repo, save_path, token=token)

            update_version_in_config(owner, repo, latest_version)

        elif version != latest_version:
            assets = release.get('assets', [])
            files_to_download = [asset['name'] for asset in assets] if not files else files

            for asset in assets:
                file_name = asset['name']
                if any(fnmatch.fnmatch(file_name, pattern) for pattern in files_to_download):
                    file_url = asset['browser_download_url']
                    download_and_unzip(file_url, save_path, file_name, token)

            update_version_in_config(owner, repo, latest_version)

        else:
            logging.info(f"项目 {owner}/{repo} 本地版本为 {version}, 已是最新, 将跳过下载")

    except Exception as e:
        logging.error(f"处理 Release 时发生错误: {e}")


def process_github_artifact(owner, repo, save_path, token=None):
    """下载 GitHub 的 Artifact 文件

    根据提供的 owner 和 repo 下载最新的 Artifact 文件。

    参数:
        owner (str): GitHub 仓库的拥有者。
        repo (str): GitHub 仓库的名称。
        save_path (str): 下载文件保存的路径。
        token (str, optional): GitHub API Token，用于身份验证。默认为 None。
    """
    url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/actions/artifacts"

    try:
        response = make_request(url, token)
        if response is None:
            return

        artifacts = response.json().get('artifacts', [])
        if artifacts:
            latest_artifact = artifacts[0]
            artifact_url = latest_artifact['archive_download_url']
            artifact_name = f"{latest_artifact['name']}.zip"

            download_and_unzip(artifact_url, save_path, artifact_name, token)
        else:
            logging.info("未找到 Artifact 文件。")
    except Exception as e:
        logging.error(f"处理 Github Artifact 时, 发生错误: {e}")


def process_github_file(owner, repo, save_path, folder=None, files=None, token=None):
    """从 GitHub Raw 下载文件，保留文件夹结构，并覆盖已存在的文件

    根据提供的 owner 和 repo 下载指定文件或文件夹。

    参数:
        owner (str): GitHub 仓库的拥有者。
        repo (str): GitHub 仓库的名称。
        save_path (str): 下载文件保存的路径。
        folder (str, optional): 指定的文件夹路径。默认为 None。
        files (list, optional): 要下载的文件名列表。默认为 None，表示下载所有文件。
        token (str, optional): GitHub API Token，用于身份验证。默认为 None。
    """

    def download_from_url(file_url, file_path):
        """从 URL 下载单个文件并覆盖已存在的文件

        参数:
            file_url (str): 文件的下载链接。
            file_path (str): 要保存的文件路径。
        """
        file_name = os.path.basename(file_path)
        file_dir = os.path.dirname(file_path)

        if not os.path.exists(file_dir):
            os.makedirs(file_dir, exist_ok=True)

        download_and_unzip(file_url, file_dir, file_name, token)

    def fetch_files_in_folder(folder_url):
        """获取指定文件夹中的所有文件，以便进行通配符匹配

        参数:
            folder_url (str): 要获取文件夹内容的 URL。

        返回:
            list: 文件夹中的文件列表。
        """
        response = make_request(folder_url, token)
        if response is None:
            return []
        return response.json()

    def download_folder_contents(folder_url, folder_path, ignore_folder_structure):
        """递归下载文件夹中的所有文件和子文件夹

        参数:
            folder_url (str): 文件夹的 URL。
            folder_path (str): 保存文件的路径。
            ignore_folder_structure (bool): 是否忽略文件夹结构。
        """
        try:
            contents = fetch_files_in_folder(folder_url)

            for item in contents:
                item_path = os.path.join(folder_path, item['name'])
                if item['type'] == 'file':
                    file_url = item['download_url']
                    if files:
                        for file_pattern in files:
                            if fnmatch.fnmatch(item['name'], file_pattern):
                                download_from_url(file_url, item_path)
                                break
                    else:
                        download_from_url(file_url, item_path)
                elif item['type'] == 'dir':
                    subfolder_url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/contents/{item['path']}"
                    new_folder_path = item_path if not ignore_folder_structure else folder_path
                    download_folder_contents(subfolder_url, new_folder_path, ignore_folder_structure)
        except Exception as e:
            logging.error(f"下载 GitHub 文件夹 {folder_path} 时发生错误: {e}")

    try:
        folder_url = (f"{GITHUB_API_URL}/repos/{owner}/{repo}/contents{folder}"
                      if folder
                      else f"{GITHUB_API_URL}/repos/{owner}/{repo}/contents")

        folder_path = os.path.normpath(save_path) if folder.startswith('/') else os.path.normpath(
            os.path.join(save_path, folder))
        os.makedirs(folder_path, exist_ok=True)

        download_folder_contents(folder_url, folder_path, folder.startswith('/'))

    except Exception as e:
        logging.error(f"下载 GitHub 文件时发生错误: {e}")


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
    save_path = os.path.abspath(save_path)
    file_save_path = os.path.join(save_path, file_name)
    older_version_file_path = os.path.join(save_path, f"【旧版本, 请手动删除】{file_name}")

    logging.info(f"准备下载文件：{file_name} 到 {save_path}")
    logging.info(f"下载链接为: {url}")

    def is_file_locked(file_path):
        """检查文件是否被锁定（使用中）

        尝试以追加模式打开文件，若失败则说明被锁定。

        参数:
            file_path (str): 要检查的文件路径。

        返回:
            bool: 文件是否被锁定。
        """
        try:
            with open(file_path, 'a'):
                return False
        except IOError:
            return True

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
            response = make_request(url, token, stream=True)
            if response is None:
                return None

            total_size = int(response.headers.get('content-length', 0)) or 1
            os.makedirs(save_path, exist_ok=True)
            file_save_path = os.path.join(save_path, file_name)

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
                        bar.update(len(chunk))

            logging.info(f"文件成功下载到: {save_path}")
            return file_save_path
        except Exception as e:
            logging.error(f"文件下载时发生错误: {e}")
            return None

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
            if file_path.endswith('.zip'):
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_path)
                logging.info(f"已成功解压 ZIP 文件: {file_name}")
            elif file_path.endswith('.7z'):
                with py7zr.SevenZipFile(file_path, mode='r') as archive:
                    archive.extractall(path=extract_path)
                logging.info(f"已成功解压 7Z 文件: {file_name}")
            elif file_path.endswith('.rar'):
                with rarfile.RarFile(file_path) as rar_ref:
                    rar_ref.extractall(extract_path)
                logging.info(f"已成功解压 RAR 文件: {file_name}")
            else:
                logging.warning(f"不支持的压缩文件格式: {file_name}")
                return False
            return True
        except Exception as e:
            logging.error(f"解压文件时发生错误: {e}")
            return False

    try:
        if os.path.isfile(file_save_path):
            if is_file_locked(file_save_path):
                logging.warning(f"{file_name} 已被占用, 尝试重命名为: 【旧版本, 请手动删除】{file_name}")
                try:
                    os.rename(file_save_path, older_version_file_path)
                    logging.info(f"现有文件已重命名为: {older_version_file_path}")
                except PermissionError:
                    logging.error(f"无法重命名文件: {file_name}, 文件可能正在被占用")
                    return False
                except Exception as e:
                    logging.error(f"重命名文件时发生错误: {e}")
                    return False
            else:
                logging.info(f"{file_name} 已存在, 但未被占用, 将直接下载并覆盖原文件")

        downloaded_file_path = download_file(url, save_path, file_name, token)
        if downloaded_file_path:
            if downloaded_file_path.endswith(('.zip', '.7z', '.rar')):
                if extract_file(downloaded_file_path, save_path):
                    os.remove(downloaded_file_path)
                    logging.info(f"已成功删除压缩文件: {file_name}")

        return True
    except Exception as e:
        logging.error(f"文件下载时发生错误: {e}")
        return False


def modify_project_status(config, project_type):
    """显示项目列表，允许用户选择项目并切换其下载功能状态

    参数:
        config (dict): 配置数据。
        project_type (str): 项目的类型（如 "release" 或 "file"）。

    返回:
        dict: 更新后的配置数据。
    """
    projects = config.get(project_type, [])

    print(f"项目列表 - {project_type.capitalize()} 项目")
    print("-" * 100)
    for i, project in enumerate(projects):
        status_symbol = '√' if project['enabled'] == "true" else '×'
        print(
            f"{i + 1}. [{status_symbol}] {'已启用' if project['enabled'] == 'true' else '未启用'}下载功能：{project['owner']}/{project['repository']}（{project.get('description', '')}）")

    print("-" * 100)
    user_input = input(
        "请选择需要启用或禁用下载功能的项目序号（可用空格、英文逗号、中文逗号、分号或斜杠中的任一分隔符分隔多个项目序号）：")
    print("-" * 100)

    selected_indices = [int(i.strip()) - 1 for i in re.split(r'[，,；;/\s]+', user_input) if i.strip().isdigit()]

    invalid_indices = [i + 1 for i in selected_indices if i < 0 or i >= len(projects)]
    if invalid_indices:
        print(f"以下序号无效：{', '.join(map(str, invalid_indices))}")
        return config

    for index in selected_indices:
        project = projects[index]
        new_status = "false" if project["enabled"] == "true" else "true"
        project["enabled"] = new_status
        logging.info(
            f"项目 {project['owner']}/{project['repository']} 的下载已{'启用' if new_status == 'true' else '禁用'}。")
        logging.info(f"{'-' * 100}")

    read_or_update_json_file(CONFIG_FILE, config)


def main():
    """主函数，执行下载任务或修改配置"""
    setup_logging(LOG_FILE)
    logging.info(f"{'=' * 100}")
    config = read_or_update_json_file(CONFIG_FILE) or {}
    logging.info(f"已读取配置文件: {CONFIG_FILE}")
    logging.info(f"{'=' * 100}")

    choice = get_user_choice(config)

    if choice == '1':
        print("=" * 100)
        process_projects(config, config.get("github_token"))

    elif choice == '2':
        print("=" * 100)
        modify_project_status(config, "release")

    elif choice == '3':
        print("=" * 100)
        modify_project_status(config, "file")

    else:
        logging.info("=" * 100)
        logging.info("无效的选择，将退出程序")
        logging.info("=" * 100)


if __name__ == "__main__":
    main()
