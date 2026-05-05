from selenium import webdriver
from selenium.webdriver.chrome.options import Options


def build_chrome_options_for_remote_debugging(*, debugger_address: str) -> Options:
    opts = Options()
    opts.add_experimental_option("debuggerAddress", debugger_address.strip())
    return opts


def chrome_driver_attach(*, debugger_address: str) -> webdriver.Chrome:
    opts = build_chrome_options_for_remote_debugging(debugger_address=debugger_address)
    return webdriver.Chrome(options=opts)
