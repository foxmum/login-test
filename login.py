import os
import json
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# 配置常量
LOGIN_URL = "https://client.webhostmost.com/login"
SUCCESS_URL = "https://client.webhostmost.com/clientarea.php"
USERNAME_SELECTOR = (By.ID, "inputEmail")    # 用户名输入框ID
PASSWORD_SELECTOR = (By.ID, "inputPassword")  # 密码输入框ID
LOGIN_BUTTON_SELECTOR = (By.ID, "login")      # 登录按钮ID
DASHBOARD_SELECTOR = (By.XPATH, "//h1[normalize-space()='Dashboard']")  # 登录后页面标志性元素

def setup_driver():
    """创建无痕模式的Chrome驱动"""
    options = webdriver.ChromeOptions()
    options.add_argument("--incognito")       # 无痕模式
    options.add_argument("--headless=new")    # 无头模式（新内核）
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    
    service = ChromeService(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {value: undefined})")
    return driver

def login_account(driver, username, password):
    """执行单个账号登录"""
    try:
        # 打开登录页
        driver.get(LOGIN_URL)
        WebDriverWait(driver, 20).until(EC.visibility_of_element_located(USERNAME_SELECTOR))
        
        # 输入账号密码
        driver.find_element(*USERNAME_SELECTOR).send_keys(username)
        driver.find_element(*PASSWORD_SELECTOR).send_keys(password)
        driver.find_element(*LOGIN_BUTTON_SELECTOR).click()
        
        # 验证登录成功：URL跳转 + 页面元素存在
        WebDriverWait(driver, 30).until(
            EC.and_(
                EC.url_to_be(SUCCESS_URL),         # 精确匹配目标URL
                EC.visibility_of_element_located(DASHBOARD_SELECTOR)
            )
        )
        print(f"登录成功：{username}")
        return True
        
    except TimeoutException:
        print(f"登录失败：{username} - 超时或URL错误")
        save_debug_info(driver, username)
        return False
    except NoSuchElementException:
        print(f"登录失败：{username} - 元素定位错误")
        save_debug_info(driver, username)
        return False
    except Exception as e:
        print(f"登录失败：{username} - 未知错误: {str(e)}")
        save_debug_info(driver, username)
        return False

def save_debug_info(driver, username):
    """保存调试信息（截图和页面源码）"""
    if driver:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"debug_{username}_{timestamp}"
        try:
            driver.save_screenshot(f"{filename}.png")
            with open(f"{filename}.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            print(f"调试信息已保存：{filename}")
        except:
            print("保存调试信息失败")

def main():
    # 从环境变量读取账号列表（JSON格式）
    accounts_json = os.getenv("ACCOUNTS_JSON")
    if not accounts_json:
        print("错误：未设置ACCOUNTS_JSON环境变量")
        exit(1)
    
    try:
        accounts = json.loads(accounts_json)
    except:
        print("错误：ACCOUNTS_JSON格式不正确")
        exit(1)
    
    success_count = 0
    for account in accounts:
        username = account.get("username")
        password = account.get("password")
        if not username or not password:
            print("错误：账号信息不完整")
            continue
        
        driver = setup_driver()
        if login_account(driver, username, password):
            success_count += 1
        driver.quit()
    
    print(f"登录结果：{success_count}/{len(accounts)} 成功")
    if success_count != len(accounts):
        exit(1)

if __name__ == "__main__":
    main()
