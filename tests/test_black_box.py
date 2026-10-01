"""
Black-Box Test Cases (Selenium)

PREREQUISITES
    1. Google Chrome must be installed.
    2. In one terminal, start the app:
           cd SEM_project/app
           python3 database.py      # reset DB + seed technicians
           python3 ml_model.py      # retrain + register model
           python3 app.py           # starts Flask on http://127.0.0.1:5000
    3. In another terminal:
           pip install selenium pytest --break-system-packages   (or via uv)
           pytest tests/test_black_box.py -v

"""

import time

import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException

BASE_URL = "http://127.0.0.1:5000"


@pytest.fixture
def driver():
    options = webdriver.ChromeOptions()
#    options.add_argument("--headless=new")
    d = webdriver.Chrome(options=options)
    d.implicitly_wait(3)
    yield d
    d.quit()


def wait_for_text_in_element(driver, element_id, expected_text, timeout=5):
    """
    Waits for expected_text to appear inside the element with element_id,
    re-fetching the element fresh on every poll. This tolerates the case
    where a form submit causes a full page navigation: the element with
    that id may exist on BOTH the pre- and post-navigation pages, so a
    plain "is it present" check can grab a reference to the old page's
    element right before it's torn down (-> StaleElementReferenceException
    on the next call). Re-querying each poll sidesteps that race.
    """
    def _check(d):
        try:
            return expected_text in d.find_element(By.ID, element_id).text
        except StaleElementReferenceException:
            return False

    WebDriverWait(driver, timeout).until(_check)


def js_click(driver, element):
    """
    Click via JS instead of WebDriver's native click.
    Chrome headless can leave a stale rendering artifact after a native
    <select> interaction that intercepts the very next real click; a JS
    click sidesteps that without changing what the click actually does.
    """
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
    driver.execute_script("arguments[0].click();", element)


def set_select_value(driver, element_id, value):
    """
    Set a <select>'s value directly via JS and fire a change event,
    instead of driving Chrome's native dropdown UI (which is the other
    source of the click-interception flakiness above).
    """
    driver.execute_script(
        "const el = document.getElementById(arguments[0]); "
        "el.value = arguments[1]; "
        "el.dispatchEvent(new Event('change'));",
        element_id, value,
    )


def login_as_iot_engineer(driver):
    driver.get(f"{BASE_URL}/login")
    driver.find_element(By.ID, "username-input").send_keys("iot_engineer")
    driver.find_element(By.ID, "password-input").send_keys("iot123")
    js_click(driver, driver.find_element(By.ID, "login-btn"))


def login_as_manager(driver):
    driver.get(f"{BASE_URL}/login")
    driver.find_element(By.ID, "username-input").send_keys("manager")
    driver.find_element(By.ID, "password-input").send_keys("mgr123")
    js_click(driver, driver.find_element(By.ID, "login-btn"))


def login_as_technician(driver, specialization_substring="MRI"):
    """
    Switches to the technician tab, waits for Bootstrap's JS to have
    actually wired up the tab (not just for the page to have loaded since
    the CDN script can still be downloading at that point), then picks
    a technician whose name/specialization contains the given substring.
    """
    driver.get(f"{BASE_URL}/login")

    WebDriverWait(driver, 10).until(
        lambda d: d.execute_script("return typeof bootstrap !== 'undefined';")
    )
    js_click(driver, driver.find_element(By.ID, "tab-technician"))
    WebDriverWait(driver, 5).until(
        EC.visibility_of_element_located((By.ID, "technician-select"))
    )

    select_el = driver.find_element(By.ID, "technician-select")
    options = select_el.find_elements(By.TAG_NAME, "option")
    match = next(o for o in options if specialization_substring in o.text)
    set_select_value(driver, "technician-select", match.get_attribute("value"))

    js_click(driver, driver.find_element(By.ID, "technician-login-btn"))


def submit_reading(driver, **field_overrides):
    fields = dict(
        equipment_id="MRI-SEL-01", equipment_type="MRI", cycle="10",
        temperature_c="20.0", vibration_mm_s="1.0", pressure_kpa="100.0",
        coolant_level_pct="90.0", power_draw_kw="30.0", usage_hours_cum="80.0",
    )
    fields.update(field_overrides)

    id_map = {
        "equipment_id": "equipment-id-input", "cycle": "cycle-input",
        "temperature_c": "temperature-input", "vibration_mm_s": "vibration-input",
        "pressure_kpa": "pressure-input", "coolant_level_pct": "coolant-input",
        "power_draw_kw": "power-input", "usage_hours_cum": "usage-hours-input",
    }
    for key, input_id in id_map.items():
        el = driver.find_element(By.ID, input_id)
        el.clear()
        el.send_keys(fields[key])

    set_select_value(driver, "equipment-type-select", fields["equipment_type"])
    js_click(driver, driver.find_element(By.ID, "submit-reading-btn"))


# 1-2: Login page basics

def test_01_login_page_loads(driver):
    driver.get(f"{BASE_URL}/login")
    assert "Login" in driver.title or driver.find_element(By.ID, "login-btn")


def test_02_invalid_staff_login_shows_error(driver):
    driver.get(f"{BASE_URL}/login")
    driver.find_element(By.ID, "username-input").send_keys("iot_engineer")
    driver.find_element(By.ID, "password-input").send_keys("wrong-password")
    driver.find_element(By.ID, "login-btn").click()
    error = WebDriverWait(driver, 5).until(
        EC.presence_of_element_located((By.ID, "flash-error"))
    )
    assert "Invalid username or password" in error.text


# 3-4: Role-based access control

def test_03_iot_engineer_login_reaches_dashboard(driver):
    login_as_iot_engineer(driver)
    heading = WebDriverWait(driver, 5).until(
        EC.presence_of_element_located((By.ID, "telemetry-form"))
    )
    assert heading is not None


def test_04_technician_cannot_access_manager_dashboard(driver):
    login_as_technician(driver)

    # a technician session trying to reach the manager URL directly
    driver.get(f"{BASE_URL}/manager/dashboard")
    error = WebDriverWait(driver, 5).until(
        EC.presence_of_element_located((By.ID, "flash-error"))
    )
    assert "don't have access" in error.text


# 5-7: The core alert flow, driven purely through the UI

def test_05_healthy_reading_shows_success_no_alert(driver):
    login_as_iot_engineer(driver)
    submit_reading(driver, equipment_id="MRI-SEL-HEALTHY", cycle="5")
    msg = WebDriverWait(driver, 5).until(
        EC.presence_of_element_located((By.ID, "flash-success"))
    )
    assert "No alert needed" in msg.text


def test_06_degraded_reading_shows_alert_banner(driver):
    login_as_iot_engineer(driver)
    submit_reading(
        driver, equipment_id="MRI-SEL-DEGRADED", cycle="280",
        temperature_c="29", vibration_mm_s="5.0", pressure_kpa="88",
        coolant_level_pct="60", power_draw_kw="43", usage_hours_cum="2200",
    )
    alert = WebDriverWait(driver, 5).until(
        EC.presence_of_element_located((By.ID, "flash-alert"))
    )
    assert "ALERT" in alert.text
    assert "auto-scheduled" in alert.text


def test_07_degraded_reading_appears_in_telemetry_table(driver):
    login_as_iot_engineer(driver)
    submit_reading(driver, equipment_id="MRI-SEL-TABLECHECK", cycle="6")
    wait_for_text_in_element(driver, "telemetry-table", "MRI-SEL-TABLECHECK")


# 8: Manager dashboard reflects the alert raised above

def test_08_manager_dashboard_shows_model_metrics_and_alert(driver):
    login_as_manager(driver)
    panel = WebDriverWait(driver, 5).until(
        EC.presence_of_element_located((By.ID, "model-info-panel"))
    )
    assert "RMSE" in panel.text
    maintenance_table = driver.find_element(By.ID, "all-maintenance-table")
    assert "scheduled" in maintenance_table.text or "completed" in maintenance_table.text


# 9-10: Technician completes an assigned work order end-to-end

def test_09_technician_sees_assigned_work_order(driver):
    # first, guarantee at least one alert exists for the MRI technician
    login_as_iot_engineer(driver)
    submit_reading(
        driver, equipment_id="MRI-SEL-FORTECH", cycle="290",
        temperature_c="30", vibration_mm_s="5.2", pressure_kpa="86",
        coolant_level_pct="55", power_draw_kw="44", usage_hours_cum="2300",
    )
    driver.get(f"{BASE_URL}/logout")

    login_as_technician(driver, specialization_substring="MRI")

    wait_for_text_in_element(driver, "work-orders-table", "MRI-SEL-FORTECH")


def test_10_technician_can_mark_work_order_complete(driver):
    login_as_technician(driver, specialization_substring="MRI")

    complete_buttons = driver.find_elements(By.CLASS_NAME, "complete-btn")
    if not complete_buttons:
        pytest.skip("No open work orders to complete -- run test_06 or test_09 first")

    driver.execute_script("arguments[0].click();", complete_buttons[0])
    msg = WebDriverWait(driver, 5).until(
        EC.presence_of_element_located((By.ID, "flash-success"))
    )
    assert "marked complete" in msg.text