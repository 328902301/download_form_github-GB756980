import os
import json
import py7zr
import zipfile
import urllib3
import logging
import requests
from tqdm import tqdm

# 设置日志配置
log_file = "download_log.txt"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename=log_file,
    datefmt='%Y-%m-%d %H:%M:%S'
)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
console_handler.setFormatter(formatter)
logging.getLogger().addHandler(console_handler)

# 禁用不安全请求的警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CONFIG_FILE = "config.json"  # 配置文件名

def read_or_update_json_file(file_name, data=None):
    """
    读取或更新 JSON 文件。

    :param file_name: JSON 文件的名称
    :param data: 要写入 JSON 文件的数据，如果为 None，则表示读取文件
    :return: 读取的 JSON 数据
    """
    try:
        if data is None:
            # 读取 JSON 文件
            with open(file_name, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            # 更新 JSON 文件
            with open(file_name, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            logging.info(f"更新 JSON 文件: {file_name}")
    except (json.JSONDecodeError, IOError, Exception) as e:
        logging.error(f"操作 JSON 文件时发生错误: {e}")

def download_and_unzip(url, save_path, file_name, token=None):
    """
    下载并解压文件。

    :param url: 文件的下载链接
    :param save_path: 文件保存路径
    :param file_name: 文件名称
    :param token: GitHub 访问令牌（可选）
    """
    file_save_path = os.path.join(save_path, file_name)
    older_version_file_path = os.path.join(save_path, f"【旧版本, 请手动删除】{file_name}")

    logging.info(f"准备下载文件：{file_name} 到 {save_path}")
    logging.info(f"下载链接为: {url}")

    headers = {}
    if token:
        headers['Authorization'] = f'token {token}'

    try:
        def is_file_locked(file_path):
            """
            检查文件是否被锁定。

            :param file_path: 文件路径
            :return: 如果文件被锁定，则返回 True，否则返回 False
            """
            try:
                with open(file_path, 'a'):
                    return False
            except IOError:
                return True

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

        # 下载文件
        response = requests.get(url, headers=headers, stream=True, verify=False)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        os.makedirs(save_path, exist_ok=True)
        with open(file_save_path, 'wb') as f, tqdm(
                desc=file_name,
                total=total_size,
                unit='iB',
                unit_scale=True,
                unit_divisor=1024,
                ncols=100,
                ascii=True) as bar:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    bar.update(len(chunk))

        logging.info(f"文件成功下载到: {file_save_path}")

        # 解压文件
        if file_name.endswith('.zip'):
            with zipfile.ZipFile(file_save_path, 'r') as zip_ref:
                zip_ref.extractall(save_path)
            logging.info(f"已成功解压文件: {file_name}")
        elif file_name.endswith('.7z'):
            with py7zr.SevenZipFile(file_save_path, mode='r') as archive:
                archive.extractall(path=save_path)
            logging.info(f"已成功解压文件: {file_name}")

    except requests.exceptions.RequestException as e:
        logging.error(f"下载文件失败: {file_name}. 错误信息: {e}")
        return False
    except Exception as e:
        logging.error(f"文件下载时发生错误: {e}")
        return False

    finally:
        # 删除压缩文件
        if file_name.endswith('.zip') or file_name.endswith('.7z'):
            if os.path.exists(file_save_path):
                os.remove(file_save_path)
                logging.info(f"已成功删除压缩文件: {file_save_path}")

def download_github_release(owner, repo, version, save_path, files=None, token=None):
    """
    下载 GitHub Release 的文件。

    :param owner: GitHub 仓库所有者
    :param repo: GitHub 仓库名称
    :param version: 版本号或 "CI" 表示最新版本
    :param save_path: 文件保存路径
    :param files: 要下载的文件列表（可选）
    :param token: GitHub 访问令牌（可选）
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    headers = {'Authorization': f'token {token}'} if token else {}

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        release = response.json()
        latest_version = release.get('tag_name', 'unknown')

        if version == "CI":
            logging.info(f"项目 {owner}/{repo} 版本号为CI, 将优先下载最新 Release")
            assets = release.get('assets', [])
            if assets:
                for asset in assets:
                    file_name = asset['name']
                    file_url = asset['browser_download_url']
                    download_and_unzip(file_url, save_path, file_name, token)
            else:
                # 如果没有 release 资产, 下载最新 artifact
                logging.info(f"项目 {owner}/{repo} 没有可用的 Release, 尝试下载最新的 Artifact")
                download_github_artifact(owner, repo, save_path, token=token)
        elif version != latest_version:
            assets = release.get('assets', [])
            files_to_download = [asset['name'] for asset in assets] if not files else files

            for asset in assets:
                file_name = asset['name']
                if file_name in files_to_download:
                    file_url = asset['browser_download_url']
                    download_and_unzip(file_url, save_path, file_name, token)

            # 更新版本信息
            data = read_or_update_json_file(CONFIG_FILE) or {}
            for project in data.get("release", []):
                if project.get("owner") == owner and project.get("repository") == repo:
                    project["version"] = latest_version
            read_or_update_json_file(CONFIG_FILE, data)
        else:
            logging.info(f"项目 {owner}/{repo} 本地版本为 {version}, 已是最新, 将跳过下载")
    except (requests.exceptions.RequestException, Exception) as e:
        logging.error(f"处理 Release 时发生错误: {e}")

def download_github_artifact(owner, repo, save_path, token=None):
    """
    下载 GitHub 的 artifact 文件。

    :param owner: GitHub 仓库所有者
    :param repo: GitHub 仓库名称
    :param save_path: 文件保存路径
    :param token: GitHub 访问令牌（可选）
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/artifacts"
    headers = {'Authorization': f'token {token}'} if token else {}

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        artifacts = response.json().get('artifacts', [])
        if artifacts:
            latest_artifact = artifacts[0]  # 假设第一个 artifact 是最新的
            artifact_url = latest_artifact['archive_download_url']
            artifact_name = f"{latest_artifact['name']}.zip"  # 如有需要请修改

            download_and_unzip(artifact_url, save_path, artifact_name, token)
        else:
            logging.info("未找到 Artifact 文件。")
    except (requests.exceptions.RequestException, Exception) as e:
        logging.error(f"处理 Github Artifact 时, 发生错误: {e}")

def download_github_file(owner, repo, save_path, folder=None, files=None, token=None):
    """
    从 GitHub Raw 下载文件, 保留文件夹结构，并覆盖已存在的文件。

    :param owner: GitHub 仓库所有者
    :param repo: GitHub 仓库名称
    :param save_path: 文件保存路径
    :param folder: 文件夹路径（可选）
    :param files: 要下载的文件列表（可选）
    :param token: GitHub 访问令牌（可选）
    """
    base_url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/"
    folder_path = folder.rstrip('/') + '/' if folder else ''

    def download_from_url(file_url, file_path):
        """
        下载单个文件并覆盖已存在的文件。

        :param file_url: 文件的下载链接
        :param file_path: 文件保存路径
        """
        file_name = os.path.basename(file_path)
        file_dir = os.path.dirname(file_path)

        # 确保目录存在
        if not os.path.exists(file_dir):
            os.makedirs(file_dir, exist_ok=True)

        # 下载文件并覆盖
        download_and_unzip(file_url, file_dir, file_name, token)

    def download_folder_contents(folder_url, folder_path):
        """
        递归下载文件夹中的所有文件和子文件夹。

        :param folder_url: 文件夹的 URL
        :param folder_path: 文件夹保存路径
        """
        try:
            response = requests.get(folder_url, headers={'Authorization': f'token {token}'} if token else {})
            response.raise_for_status()
            contents = response.json()

            for item in contents:
                item_path = os.path.join(folder_path, item['name'])
                if item['type'] == 'file':
                    file_url = item['download_url']
                    file_path = os.path.normpath(item_path)
                    download_from_url(file_url, file_path)
                elif item['type'] == 'dir':
                    subfolder_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{item['path']}"
                    subfolder_path = os.path.normpath(item_path)
                    os.makedirs(subfolder_path, exist_ok=True)
                    download_folder_contents(subfolder_url, subfolder_path)
        except requests.exceptions.RequestException as e:
            logging.error(f"下载 GitHub 文件夹 {folder_path} 时发生错误: {e}")

    try:
        if files:  # 如果需要下载指定文件
            for file_name in files:
                if folder:
                    file_url = f"{base_url}{folder_path}{file_name}"
                    file_path = os.path.normpath(os.path.join(save_path, file_name))
                else:
                    file_url = f"{base_url}{file_name}"
                    file_path = os.path.normpath(os.path.join(save_path, file_name))

                download_from_url(file_url, file_path)
        else:  # 如果没有指定文件, 下载文件夹中的所有文件
            folder_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{folder_path}"
            full_save_path = os.path.normpath(os.path.join(save_path, folder_path))
            os.makedirs(full_save_path, exist_ok=True)
            download_folder_contents(folder_url, full_save_path)
    except requests.exceptions.RequestException as e:
        logging.error(f"下载 GitHub 文件时发生错误: {e}")

def main():
    """
    主函数, 执行下载任务。
    """
    logging.info(f"{'=' * 50}")  # 分隔线
    config = read_or_update_json_file(CONFIG_FILE)
    logging.info(f"已读取配置文件: {CONFIG_FILE}")  # 记录读取配置文件的日志
    logging.info(f"{'=' * 50}")  # 分隔线

    github_token = config.get("github_token")

    if github_token:
        logging.info("已从 config.json 中加载 GitHub Token")
        logging.info(f"{'=' * 50}")  # 分隔线
    else:
        logging.warning("未在 config.json 中配置 GitHub Token, 下载时将不携带Github Token")
        logging.info(f"{'=' * 50}")  # 分隔线

    logging.info("即将开始更新 Github 最新 Release")
    logging.info(f"{'=' * 50}")  # 分隔线
    for project in config.get("release", []):
        if project.get("enabled") == "true":
            owner = project.get("owner")
            repo = project.get("repository")
            version = project.get("version")
            save_path = os.path.expandvars(project.get("save_path"))
            files = project.get("files")
            logging.info(f"即将处理项目: {owner}/{repo}")
            download_github_release(owner, repo, version, save_path, files, github_token)
            logging.info(f"当前项目已处理完成: {owner}/{repo}")
            logging.info(f"{'-' * 83}")  # 分隔线
        else:
            logging.info(f"项目 {project.get('owner')}/{project.get('repository')} 未启用下载功能, 将跳过下载")
            logging.info(f"{'-' * 83}")  # 分隔线

    logging.info("Github 最新 Release已更新完成")
    logging.info(f"{'=' * 50}")  # 分隔线

    logging.info("即将开始下载 Github 文件")
    logging.info(f"{'=' * 50}")  # 分隔线
    for project in config.get("file", []):
        if project.get("enabled") == "true":
            owner = project.get("owner")
            repo = project.get("repository")
            save_path = os.path.expandvars(project.get("save_path"))
            folder = project.get("folder")
            files = project.get("files")

            logging.info(f"即将处理项目: {owner}/{repo}")
            download_github_file(owner, repo, save_path, folder, files, github_token)
            logging.info(f"当前项目已处理完成: {owner}/{repo}")
            logging.info(f"{'-' * 83}")  # 分隔线
        else:
            logging.info(f"项目 {project.get('owner')}/{project.get('repository')} 未启用下载功能, 将跳过下载")
            logging.info(f"{'-' * 83}")  # 分隔线

    logging.info("Github 最新文件已下载完成")
    logging.info(f"{'=' * 50}")  # 分隔线

if __name__ == "__main__":
    main()