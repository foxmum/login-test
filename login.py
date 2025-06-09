import os
import json
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementNotInteractableException, StaleElementReferenceException

LOGIN_URL = "https://client.webhostmost.com/login"

# --- Element Selectors ---
# It's crucial these are correct. Inspect the page if issues persist.
USERNAME_SELECTOR = (By.ID, "inputEmail")
PASSWORD_SELECTOR = (By.ID, "inputPassword")

# Option 1: Try by specific ID if available (usually most reliable)
# LOGIN_BUTTON_SELECTOR = (By.ID, "login") # Replace "login" with actual ID if found
# Option 2: The XPath you provided.
LOGIN_BUTTON_SELECTOR = (By.XPATH, "//button[@type='submit' and (contains(text(),'Login') or @id='login' or contains(@class,'btn-primary'))]") # Made it more general
# Option 3: Simpler XPath if the text is reliable
# LOGIN_BUTTON_SELECTOR = (By.XPATH, "//button[contains(normalize-space(.), 'Login')]")


# After login attempt, look for these:
# It's better to target a specific element if possible, e.g., a h1 title or a specific div.
SUCCESS_INDICATOR_SELECTOR = (By.XPATH, "//*[self::h1 or self::h2 or self::div[@class='title']][contains(normalize-space(.), 'Client Area')]") # Example, adjust as needed
# For the error message "Login Details Incorrect. Please try again."
FAILURE_INDICATOR_SELECTOR = (By.XPATH, "//*[contains(@class, 'alert-danger') or contains(@class, 'alert-warning')][contains(normalize-space(.), 'Login Details Incorrect')]")


def setup_driver():
    """配置并返回一个 Selenium WebDriver 实例"""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920x1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36")
    options.add_argument("--disable-blink-features=AutomationControlled") # Try to appear less like a bot
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)

    try:
        print("Attempting to install/setup ChromeDriver using ChromeDriverManager...")
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        print("ChromeDriver setup successfully via ChromeDriverManager.")
    except Exception as e:
        print(f"Error setting up ChromeDriverManager: {e}")
        print("Attempting to find ChromeDriver in PATH as a fallback...")
        try:
            driver = webdriver.Chrome(options=options)
            print("ChromeDriver setup successfully from PATH.")
        except Exception as e2:
            print(f"Critical Error: Could not initialize Chrome WebDriver: {e2}")
            raise
    
    # Mitigate detection
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def save_debug_info(driver, username, stage="error"):
    """Saves screenshot and page source for debugging."""
    safe_username = "".join(c if c.isalnum() else "_" for c in username)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    screenshot_path = f"{stage}_{safe_username}_{timestamp}.png"
    page_source_path = f"{stage}_source_{safe_username}_{timestamp}.html"

    print(f"Saving debug information for {username} at stage '{stage}'.")
    print(f"Current URL: {driver.current_url}")
    print(f"Current page title: '{driver.title}'")
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


def login(driver, username, password):
    """执行登录操作"""
    print(f"Attempting to log in as {username}...")

    try:
        print(f"Navigating to login page: {LOGIN_URL}")
        driver.get(LOGIN_URL)
        time.sleep(2) # Allow initial page load, JS etc.
        
        print(f"Page title after load: '{driver.title}'")
        print(f"Current URL after load: {driver.current_url}")

        # Wait for username field, clear and send keys
        print(f"Waiting for username field with selector: {USERNAME_SELECTOR}")
        username_field = WebDriverWait(driver, 15).until(
            EC.visibility_of_element_located(USERNAME_SELECTOR)
        )
        print("Username field found. Clearing and sending keys.")
        username_field.clear()
        username_field.send_keys(username)

        # Wait for password field, clear and send keys
        print(f"Waiting for password field with selector: {PASSWORD_SELECTOR}")
        password_field = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located(PASSWORD_SELECTOR)
        )
        print("Password field found. Clearing and sending keys.")
        password_field.clear()
        password_field.send_keys(password)
        
        # Save info before clicking login
        # save_debug_info(driver, username, "before_login_click")

        # Attempt to click the login button
        print(f"Attempting to click login button with selector: {LOGIN_BUTTON_SELECTOR}")
        try:
            login_button = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable(LOGIN_BUTTON_SELECTOR)
            )
            print("Login button found and deemed clickable. Clicking.")
            # Try JavaScript click if direct click fails sometimes
            driver.execute_script("arguments[0].click();", login_button)
            # login_button.click() 
        except TimeoutException:
            print("Login button not 'clickable' within timeout. Trying to find and click directly.")
            try:
                login_button = driver.find_element(*LOGIN_BUTTON_SELECTOR)
                print("Login button found (not necessarily clickable). Attempting direct click.")
                # Try JavaScript click if direct click fails sometimes
                driver.execute_script("arguments[0].click();", login_button)
                # login_button.click()
            except (NoSuchElementException, ElementNotInteractableException) as e_click:
                print(f"Could not find or interact with login button after timeout: {e_click}")
                save_debug_info(driver, username, "login_button_fail")
                return False
        
        print("Login button click attempted. Waiting for success or failure indicator (20s timeout)...")
        
        # Wait for EITHER success OR failure indicator
        WebDriverWait(driver, 20).until(
            EC.any_of(
                EC.presence_of_element_located(SUCCESS_INDICATOR_SELECTOR),
                EC.presence_of_element_located(FAILURE_INDICATOR_SELECTOR)
            )
        )

        # Check for success indicator
        try:
            success_element = driver.find_element(*SUCCESS_INDICATOR_SELECTOR)
            if success_element.is_displayed():
                print(f"Successfully logged in as {username}. Found success indicator: '{success_element.text[:100]}...'")
                # save_debug_info(driver, username, "login_success") # Optional: save info on success
                return True
        except NoSuchElementException:
            pass # Success indicator not found, proceed to check failure

        # Check for failure indicator
        try:
            failure_element = driver.find_element(*FAILURE_INDICATOR_SELECTOR)
            if failure_element.is_displayed():
                print(f"Login failed for {username}. Found failure indicator: '{failure_element.text[:100]}...'")
                save_debug_info(driver, username, "login_failed_message")
                return False
        except NoSuchElementException:
            pass # Failure indicator not found either

        # If neither success nor failure indicator is found after the wait
        print(f"Login outcome unclear for {username}. Neither success nor specific failure message found.")
        print(f"Current URL: {driver.current_url}, Page Title: '{driver.title}'")
        save_debug_info(driver, username, "login_outcome_unclear")
        return False

    except TimeoutException as te:
        print(f"A timeout occurred during login process for {username}: {str(te).splitlines()[0]}")
    except NoSuchElementException as nse:
        print(f"An element was not found during login process for {username}: {str(nse).splitlines()[0]}")
    except ElementNotInteractableException as enie:
        print(f"An element was not interactable during login process for {username}: {str(enie).splitlines()[0]}")
    except StaleElementReferenceException as sere:
        print(f"A stale element reference occurred for {username}: {str(sere).splitlines()[0]}. Page might have reloaded unexpectedly.")
    except Exception as e:
        print(f"An unexpected error occurred during login for {username}: {type(e).__name__} - {str(e)}")
    
    save_debug_info(driver, username, "login_exception") # Save debug info if any exception not caught cleanly above
    return False

def main():
    accounts_json_str = os.environ.get("ACCOUNTS_JSON")
    if not accounts_json_str:
        print("Error: ACCOUNTS_JSON environment variable not set.")
        # For local testing, you can provide a default or read from a file
        # accounts_json_str = '[{"username": "your_test_user", "password": "your_test_password"}]'
        # if not accounts_json_str:
        return

    try:
        accounts = json.loads(accounts_json_str)
    except json.JSONDecodeError:
        print(f"Error: ACCOUNTS_JSON is not valid JSON. Content was: {accounts_json_str}")
        return

    if not isinstance(accounts, list) or not all(isinstance(acc, dict) for acc in accounts):
        print("Error: ACCOUNTS_JSON should be a JSON array of objects (list of dicts).")
        return
    
    if not accounts:
        print("No accounts found in ACCOUNTS_JSON. Exiting.")
        return

    driver = None
    overall_success = True
    try:
        driver = setup_driver()
        for i, account in enumerate(accounts):
            username = account.get("username")
            password = account.get("password")

            if not username or not password:
                print(f"Warning: Skipping account #{i+1} due to missing username or password.")
                overall_success = False
                continue
            
            print(f"\nProcessing account #{i+1} of {len(accounts)}: {username}")
            login_successful = login(driver, username, password)
            if login_successful:
                print(f"Post-login actions (if any) for {username} would be here.")
                # Example: driver.get("https://client.webhostmost.com/clientarea.php?action=details")
                # time.sleep(5) # wait for page
                # print(f"On account details page for {username}")
            else:
                overall_success = False
                print(f"Login attempt concluded for {username} with failure or error.")
            
            print("-" * 50)
            if i < len(accounts) - 1 :
                time.sleep(3) # Brief pause between accounts, also allows some state to clear if needed

    except Exception as e:
        print(f"A critical error occurred in the main execution block: {type(e).__name__} - {str(e)}")
        overall_success = False
    finally:
        if driver:
            driver.quit()
            print("Browser closed.")
    
    if not overall_success:
        print("\nATTENTION: One or more logins failed or a critical error occurred. Review logs and artifacts.")
        # If running in GitHub Actions, the YAML already handles failing the job based on script exit code
        # If you want to ensure this script itself signals failure for other CI systems:
        # exit(1) 
    else:
        print("\nAll account login attempts processed.")

if __name__ == "__main__":
    main()
