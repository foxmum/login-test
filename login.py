import os
import json
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementNotInteractableException

LOGIN_URL = "https://client.webhostmost.com/login"
# 确认这些选择器仍然准确无误
USERNAME_SELECTOR = (By.ID, "inputEmail") 
PASSWORD_SELECTOR = (By.ID, "inputPassword") 
LOGIN_BUTTON_SELECTOR = (By.XPATH, "//button[@type='submit' and contains(text(),'Login')]")
SUCCESS_URL_PART = "clientarea.php" # 登录成功后URL会包含 clientarea.php

def setup_driver():
    """配置并返回一个 Selenium WebDriver 实例"""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920x1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36")

    try:
        print("Attempting to install/setup ChromeDriver using ChromeDriverManager...")
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        print("ChromeDriver setup successfully via ChromeDriverManager.")
    except Exception as e:
        print(f"Error setting up ChromeDriverManager: {e}")
        print("Attempting to find ChromeDriver in PATH as a fallback...")
        try:
            driver = webdriver.Chrome(options=options) # 尝试使用系统路径中的 ChromeDriver
            print("ChromeDriver setup successfully from PATH.")
        except Exception as e2:
            print(f"Critical Error: Could not initialize Chrome WebDriver: {e2}")
            raise # 如果两种方式都失败，则抛出异常
            
    return driver

def login(driver, username, password):
    """执行登录操作"""
    print(f"Attempting to log in as {username}...")
    # 清理用户名以便用于文件名
    safe_username = "".join(c if c.isalnum() else "_" for c in username)
    screenshot_path = f"login_attempt_{safe_username}.png"
    page_source_path = f"login_attempt_source_{safe_username}.html"

    try:
        print(f"Navigating to login page: {LOGIN_URL}")
        driver.get(LOGIN_URL)
        time.sleep(2) # 给页面一点额外时间加载JS等
        
        print(f"Page title after load: '{driver.title}'")
        print(f"Current URL after load: {driver.current_url}")

        print(f"Waiting for username field with selector: {USERNAME_SELECTOR}")
        username_field = WebDriverWait(driver, 20).until(
            EC.visibility_of_element_located(USERNAME_SELECTOR)
        )
        print("Username field found. Clearing and sending keys.")
        username_field.clear() # 清空字段以防有预填内容
        username_field.send_keys(username)

        print(f"Waiting for password field with selector: {PASSWORD_SELECTOR}")
        password_field = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located(PASSWORD_SELECTOR)
        )
        print("Password field found. Clearing and sending keys.")
        password_field.clear()
        password_field.send_keys(password)
        
        # 截图以查看字段是否已填充
        # driver.save_screenshot(f"filled_fields_{safe_username}.png")
        # print(f"Screenshot saved to filled_fields_{safe_username}.png")

        print(f"Waiting for login button to be clickable with selector: {LOGIN_BUTTON_SELECTOR}")
        login_button = WebDriverWait(driver, 15).until( # 增加按钮等待时间
            EC.element_to_be_clickable(LOGIN_BUTTON_SELECTOR)
        )
        print("Login button found and clickable. Clicking.")
        login_button.click()

        print(f"Waiting for URL to contain '{SUCCESS_URL_PART}' after click (timeout 20s)...")
        WebDriverWait(driver, 20).until(
            EC.url_contains(SUCCESS_URL_PART)
        )
        
        print(f"Current URL after click and wait: {driver.current_url}")
        if SUCCESS_URL_PART in driver.current_url:
            print(f"Successfully logged in as {username}.")
            return True
        else:
            print(f"Login failed for {username} after click. Expected URL part '{SUCCESS_URL_PART}' not found.")
            driver.save_screenshot(screenshot_path)
            print(f"Screenshot saved to {screenshot_path}")
            with open(page_source_path, "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            print(f"Page source saved to {page_source_path}")
            return False

    except TimeoutException as te:
        print(f"A timeout occurred during login for {username}: {str(te).splitlines()[0]}") #只打印第一行
    except NoSuchElementException as nse:
        print(f"An element was not found during login for {username}: {str(nse).splitlines()[0]}")
    except ElementNotInteractableException as enie:
        print(f"An element was not interactable during login for {username}: {str(enie).splitlines()[0]}")
    except Exception as e:
        print(f"An unexpected error occurred during login for {username}: {type(e).__name__} - {str(e)}")
    
    # 如果发生任何类型的异常，保存调试信息
    print(f"Saving debug information for {username} due to error/failure.")
    print(f"Current URL at time of error: {driver.current_url}")
    print(f"Current page title at time of error: '{driver.title}'")
    try:
        driver.save_screenshot(screenshot_path)
        print(f"Screenshot saved to {screenshot_path}")
    except Exception as e_ss:
        print(f"Could not save screenshot: {e_ss}")
    try:
        with open(page_source_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print(f"Page source saved to {page_source_path}")
    except Exception as e_ps:
        print(f"Could not save page source: {e_ps}")
        
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
        print("Error: ACCOUNTS_JSON should be a JSON array of objects (list of dicts).")
        return
    
    if not accounts:
        print("No accounts found in ACCOUNTS_JSON. Exiting.")
        return

    driver = None
    all_logins_successful = True
    try:
        driver = setup_driver()
        for i, account in enumerate(accounts):
            username = account.get("username")
            password = account.get("password")

            if not username or not password:
                print(f"Warning: Skipping account #{i+1} due to missing username or password.")
                all_logins_successful = False # Consider this a failure for overall status
                continue
            
            print(f"\nProcessing account #{i+1}: {username}")
            login_successful = login(driver, username, password)
            if login_successful:
                print(f"Post-login actions (if any) for {username} would be here.")
            else:
                all_logins_successful = False
                print(f"Login failed for {username}.")
            print("-" * 40)
            if i < len(accounts) - 1 : # If not the last account
                time.sleep(3) # Brief pause between accounts

    except Exception as e:
        print(f"A critical error occurred in the main execution block: {type(e).__name__} - {e}")
        all_logins_successful = False
    finally:
        if driver:
            driver.quit()
            print("Browser closed.")
    
    if not all_logins_successful:
        print("\nOne or more logins failed or an error occurred. Review logs above and any saved artifacts.")
        # For GitHub Actions to correctly show a failed run if any login fails.
        # exit(1) # Uncomment if you want the entire job to fail if any login fails.
                # Note: The YAML already handles failing the job if the script step fails.
    else:
        print("\nAll account logins processed successfully.")


if __name__ == "__main__":
    main()
