import os
import json
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

LOGIN_URL = "https://client.webhostmost.com/login"
# 实际的CSS选择器需要你根据网页源代码确认 (使用浏览器开发者工具)
USERNAME_SELECTOR = (By.ID, "inputEmail") # 经检查，ID是inputEmail
PASSWORD_SELECTOR = (By.ID, "inputPassword") # 经检查，ID是inputPassword
LOGIN_BUTTON_SELECTOR = (By.XPATH, "//button[@type='submit' and contains(text(),'Login')]") # 经检查，是这个
# 登录成功后跳转的URL中通常包含的特征字符串，或者某个特定元素
SUCCESS_URL_PART = "clientarea.php" # 登录成功后URL会包含 clientarea.php
# 或者登录成功后页面上会有的元素
# SUCCESS_ELEMENT_SELECTOR = (By.XPATH, "//h1[contains(text(),'Dashboard')]")


def setup_driver():
    """配置并返回一个 Selenium WebDriver 实例"""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # 无头模式，在服务器上运行时不需要图形界面
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920x1080") # 设置窗口大小，有时可避免一些问题
    
    # 使用 webdriver-manager 自动管理 ChromeDriver
    try:
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
    except Exception as e:
        print(f"Error setting up ChromeDriverManager: {e}")
        print("Attempting to find ChromeDriver in PATH...")
        # 备选方案：如果 webdriver-manager 失败，尝试直接使用系统路径中的 ChromeDriver
        # 这要求 GitHub Actions runner 中已安装 ChromeDriver 并配置到 PATH
        driver = webdriver.Chrome(options=options)
        
    return driver

def login(driver, username, password):
    """执行登录操作"""
    try:
        driver.get(LOGIN_URL)
        print(f"Attempting to log in as {username}...")

        # 等待用户名输入框可见并输入
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located(USERNAME_SELECTOR)
        ).send_keys(username)

        # 等待密码输入框可见并输入
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located(PASSWORD_SELECTOR)
        ).send_keys(password)

        # 点击登录按钮
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable(LOGIN_BUTTON_SELECTOR)
        ).click()

        # 等待登录成功（通过URL变化或特定元素出现来判断）
        WebDriverWait(driver, 15).until(
            EC.url_contains(SUCCESS_URL_PART)
            # 或者使用元素判断:
            # EC.presence_of_element_located(SUCCESS_ELEMENT_SELECTOR)
        )
        
        if SUCCESS_URL_PART in driver.current_url: # 或检查特定元素是否存在
            print(f"Successfully logged in as {username}.")
            return True
        else:
            print(f"Login failed for {username}. Current URL: {driver.current_url}")
            # 可以尝试保存截图以便调试
            # driver.save_screenshot(f"login_failed_{username}.png")
            return False

    except Exception as e:
        print(f"An error occurred during login for {username}: {e}")
        # driver.save_screenshot(f"login_error_{username}.png")
        return False

def main():
    accounts_json_str = os.environ.get("ACCOUNTS_JSON")
    if not accounts_json_str:
        print("Error: ACCOUNTS_JSON environment variable not set.")
        return

    try:
        accounts = json.loads(accounts_json_str)
    except json.JSONDecodeError:
        print("Error: ACCOUNTS_JSON is not valid JSON.")
        print(f"Content was: {accounts_json_str}")
        return

    if not isinstance(accounts, list):
        print("Error: ACCOUNTS_JSON should be a JSON array of objects.")
        return

    driver = None
    try:
        driver = setup_driver()
        for account in accounts:
            username = account.get("username")
            password = account.get("password")

            if not username or not password:
                print("Warning: Skipping account with missing username or password.")
                continue
            
            login_successful = login(driver, username, password)
            if login_successful:
                # 你可以在这里添加登录成功后希望执行的其他操作
                print(f"Post-login actions (if any) for {username} completed.")
            else:
                print(f"Skipping post-login actions for {username} due to login failure.")
            print("-" * 30)
            time.sleep(2) # 短暂等待，避免请求过快

    finally:
        if driver:
            driver.quit()
            print("Browser closed.")

if __name__ == "__main__":
    main()