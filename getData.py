from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import psycopg2
import os
import re
import shutil
import time
from selenium.common.exceptions import NoSuchElementException
import socket
import logging
from logging.handlers import TimedRotatingFileHandler
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from datetime import datetime
from webdriver_manager.chrome import ChromeDriverManager


load_dotenv()

# Directory to download all the files and folder. Can be later changed to the server NAS or any other shared folder.
# Use absolute path for cross-platform compatibility (Chrome requires absolute paths for downloads)
directory = os.path.abspath("Tenders/")


# ─── PostgreSQL Setup ─────────────────────────────────────────────────────────

SEED_KEYWORDS = [
    'CCTV', 'Camera', 'Surveillance', 'LAN', 'Network', 'Firewall',
    'Fire Alarm', 'Fire detection', 'Perimeter', 'UPS', 'Access Control', 'Biometric'
]

def get_db_connection():
    """Create and return a PostgreSQL connection using DATABASE_URL from .env"""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL not found in .env file.")
    conn = psycopg2.connect(database_url)
    conn.autocommit = True
    return conn


def init_db(conn):
    """Create all required tables if they don't exist and seed keywords."""
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS keywords (
            id SERIAL PRIMARY KEY,
            keyword TEXT UNIQUE NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tenders (
            bid_no TEXT PRIMARY KEY,
            start_date TEXT,
            end_date TEXT,
            items TEXT,
            quantity TEXT,
            department_name_and_address TEXT,
            status TEXT DEFAULT 'new',
            created_at TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS representations (
            id SERIAL PRIMARY KEY,
            bid_no TEXT NOT NULL REFERENCES tenders(bid_no) ON DELETE CASCADE,
            section TEXT,
            query TEXT,
            reply TEXT,
            UNIQUE(bid_no, section, query, reply)
        );

        CREATE TABLE IF NOT EXISTS corrigendums (
            id SERIAL PRIMARY KEY,
            bid_no TEXT NOT NULL REFERENCES tenders(bid_no) ON DELETE CASCADE,
            modified_on TEXT,
            file_name TEXT,
            message TEXT,
            opening_date TEXT,
            extended_date TEXT,
            UNIQUE(bid_no, modified_on)
        );

        CREATE TABLE IF NOT EXISTS updates (
            id SERIAL PRIMARY KEY,
            bid_no TEXT NOT NULL REFERENCES tenders(bid_no) ON DELETE CASCADE,
            status TEXT,
            "timestamp" TIMESTAMP DEFAULT NOW(),
            message TEXT,
            "by" TEXT
        );

        CREATE TABLE IF NOT EXISTS bad_tenders (
            bid_no TEXT PRIMARY KEY,
            page_no INTEGER,
            idx INTEGER,
            message TEXT
        );

        CREATE TABLE IF NOT EXISTS rejected_tenders (
            id SERIAL PRIMARY KEY,
            bid_no TEXT NOT NULL,
            keyword TEXT NOT NULL,
            items TEXT,
            start_date TEXT,
            end_date TEXT,
            rejected_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(bid_no, keyword)
        );
    """)

    # Seed keywords
    for kw in SEED_KEYWORDS:
        cur.execute(
            "INSERT INTO keywords (keyword) VALUES (%s) ON CONFLICT (keyword) DO NOTHING",
            (kw,)
        )

    cur.close()


# ─── Helper Functions ─────────────────────────────────────────────────────────

def sendCriticalErrorMail(subject, message, recipientMail='info@techniki.tech'):
    senderMail = os.getenv('SENDER_MAIL')
    msg = MIMEMultipart()
    msg['To'] = 'duaadvitya@gmail.com'
    msg['Subject'] = subject
    msg['From'] = 'errors@techniki.tech'
    msg.attach(MIMEText(message, 'plain'))
    sendPass = os.getenv('SENDER_PASS')
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(senderMail, sendPass)
        server.sendmail(senderMail, 'duaadvitya@gmail.com', msg.as_string())
        logger.info("Email sent successfully via SMTP relay.")
        server.quit()
    except Exception as e:
        logger.info(f"Failed to send email via SMTP relay: {e}")


def checkInternetConnection(host="8.8.8.8", port=53, timeout=3):
    """
    Check if the internet connection is available.
    :param host: Default DNS server (Google's 8.8.8.8).
    :param port: Default port for DNS service.
    :param timeout: Time in seconds before timeout.
    :return: True if connected, False otherwise.
    """
    try:
        socket.setdefaulttimeout(timeout)
        socket.create_connection((host, port))
        return True
    except socket.error as err:
        logger.error(f"No internet connection: {err}")
        return False


def downloadBidFile(downloadButton, path_to_downloads, file_name, timeout=60, check_interval=1, retry_attempts=3):
    """
    Waits for the download to complete by checking for a specific '.crdownload' file and validates the downloaded file.
    If the file isn't found after download, it retries the download.

    Parameters:
        downloadButton: The Selenium WebElement to click for download.
        path_to_downloads (str): Path to the downloads directory.
        file_name (str): Name of the file (without prefix/suffix) to monitor.
        timeout (int): Maximum time to wait for the download to complete (in seconds).
        check_interval (int): Time interval to check for download status (in seconds).
        retry_attempts (int): Number of times to retry the download if the file isn't found.

    Returns:
        int: Time taken for the download to complete (in seconds).

    Raises:
        FileNotFoundError: If the file is not found even after retries.
    """
    target_file = f"GeM-Bidding-{file_name}.pdf"
    crdownload_file = f"{target_file}.crdownload"
    seconds = 0

    for attempt in range(retry_attempts):
        # Start the download by clicking the button
        downloadButton.click()

        # Wait for the download to complete
        while seconds < timeout:
            time.sleep(check_interval)
            # Check if the .crdownload file is not in the directory, indicating download has finished
            if crdownload_file not in os.listdir(path_to_downloads):
                # After the download completes, validate that the target file exists
                if target_file in os.listdir(path_to_downloads):
                    logger.info(f"Download completed in {seconds} seconds.")
                    return seconds
                else:
                    # If the file is not found after completion, break and retry
                    logger.error(f"File '{target_file}' not found, retrying download...")
                    break
            seconds += check_interval

        # If download fails within timeout, retry
        if seconds >= timeout:
            logger.error(f"Download did not complete in {timeout} seconds, retrying...")
            seconds = 0  # Reset seconds for next attempt

    # If the download failed even after retrying
    raise FileNotFoundError(f"File '{target_file}' not found after {retry_attempts} attempts.")


def moveSelectedFile(src_dir, dest_dir, file_name, retry_attempts=3, check_interval=2):
    """
    Moves a specific file from src_dir to dest_dir and validates the move.
    If the file is not moved, retries the move operation.

    Parameters:
        src_dir (str): Source directory containing the files.
        dest_dir (str): Destination directory to move the file.
        file_name (str): Name of the file (without prefix/suffix).
        retry_attempts (int): Number of times to retry moving the file.
        check_interval (int): Time interval between each retry (in seconds).

    Raises:
        FileNotFoundError: If the specified file is not found in the source directory.
        Exception: If the file cannot be moved after retrying.
    """
    target_file = f"GeM-Bidding-{file_name}.pdf"
    source_path = os.path.join(src_dir, target_file)
    destination_path = os.path.join(dest_dir, target_file)

    # Check if the file exists in the source directory
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"File '{target_file}' not found in {src_dir}.")

    for attempt in range(retry_attempts):
        # Move the file to the destination directory
        shutil.move(source_path, dest_dir)

        # Validate if the file is successfully moved
        if os.path.exists(destination_path):
            logger.info(f"File {target_file} successfully moved to {dest_dir}.")
            return

        # If file is not found in the destination directory, wait and retry
        logger.error(f"File {target_file} not found in {dest_dir}, retrying move...")
        time.sleep(check_interval)

    # If file is still not found after retrying
    raise Exception(f"File '{target_file}' could not be moved to {dest_dir} after {retry_attempts} attempts.")


def downloadCorrFile(downloadButton, path_to_downloads, timeout=60, check_interval=1, retry_attempts=3):
    """
    Waits for the download to complete by checking for '.crdownload' files.
    Retries the download operation if the file is not found or if the timeout occurs.

    Parameters:
        downloadButton (WebElement): The button to trigger the download.
        path_to_downloads (str): Path to the downloads directory.
        timeout (int): Maximum time to wait for the download to complete (in seconds).
        check_interval (int): Time interval to check for download status (in seconds).
        retry_attempts (int): Number of times to retry the download if it does not complete successfully.

    Returns:
        int: Time taken for the download to complete (in seconds).

    Raises:
        TimeoutError: If the download does not complete within the given timeout after retrying.
    """
    for attempt in range(retry_attempts):
        # Trigger the download
        downloadButton.click()
        seconds = 0
        downloading_file = None

        # Wait for the download to start and check for a `.crdownload` file
        while seconds < timeout:
            crdownload_files = [fname for fname in os.listdir(path_to_downloads) if fname.endswith('.crdownload')]

            if crdownload_files:
                # Capture the first file being downloaded
                downloading_file = crdownload_files[0]
                break
            time.sleep(0.01)
            seconds += 0.01

        if not downloading_file:
            logger.error("No `.crdownload` file found, retrying...")
            seconds = 0
            continue  # Retry if no download is detected

        seconds = 0
        # Now wait for the download to finish
        while seconds < timeout:
            time.sleep(check_interval)
            crdownload_files = [fname for fname in os.listdir(path_to_downloads) if fname.endswith('.crdownload')]

            if not crdownload_files:  # No `.crdownload` files means download is complete
                # Check if the final file (without `.crdownload`) exists
                completed_file = downloading_file.replace('.crdownload', '')
                if completed_file in os.listdir(path_to_downloads):
                    logger.info(f"Download completed in {seconds} seconds.")
                    return seconds
                else:
                    logger.error(f"File '{completed_file}' not found, retrying download...")
                    break  # Retry if the file is not found

            seconds += check_interval

        if seconds >= timeout:
            logger.error(f"Download did not complete in {timeout} seconds, retrying...")

        # Reset the counter and attempt again
        seconds = 0

    # If the download failed even after retrying
    raise TimeoutError("Download did not complete in the given time after retrying.")


def moveLatestFile(src_dir, dest_dir, retry_attempts=3, check_interval=2):
    """
    Moves the latest file from src_dir to dest_dir and validates the move.
    Retries if the file is not successfully moved.

    Parameters:
        src_dir (str): Source directory containing the files.
        dest_dir (str): Destination directory to move the file.
        retry_attempts (int): Number of times to retry if the file is not moved successfully.
        check_interval (int): Time interval between retries (in seconds).

    Returns:
        str: Name of the file that was moved.

    Raises:
        FileNotFoundError: If no files are found in the source directory.
    """
    for attempt in range(retry_attempts):
        # Get the list of downloaded files (excluding '.crdownload' files)
        downloaded_files = [
            os.path.join(src_dir, f) for f in os.listdir(src_dir)
            if not f.endswith('.crdownload')
        ]

        if not downloaded_files:
            raise FileNotFoundError("No downloaded file found.")

        # Find the latest file based on modification time (getctime is unreliable on Linux)
        latest_file = max(downloaded_files, key=os.path.getmtime)
        target_file = os.path.join(dest_dir, os.path.basename(latest_file))

        try:
            # Attempt to move the file
            shutil.move(latest_file, dest_dir)

            # Validate the move by checking if the file is now in the destination directory
            if os.path.exists(target_file):
                logger.info(f"File {os.path.basename(latest_file)} moved to {dest_dir}.")
                return os.path.basename(latest_file)
            else:
                logger.error(f"Move failed for {os.path.basename(latest_file)}, retrying...")
                time.sleep(check_interval)  # Wait before retrying

        except Exception as e:
            logger.error(f"Error while moving file: {e}, retrying...")

    # If the move operation is still unsuccessful after retries
    raise FileNotFoundError(f"File could not be moved after {retry_attempts} attempts.")


# ─── PostgreSQL-backed Representation & Corrigendum Search ────────────────────

def representationSearch(driver, otherDetailsElement, conn, bidNo):
    otherDetailsElement.find_element(By.XPATH, './/*[text()="View Representation"]').click()
    try:
        WebDriverWait(driver, 5).until(EC.visibility_of_element_located((By.XPATH, '//*[@id="representation_modal_ajax"]')))
        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, '//*[@id="rep_res"]/tr')))
        elements = driver.find_elements(By.XPATH, '//*[@id="rep_res"]/tr')

        cur = conn.cursor()
        for element in elements:
            section = element.find_element(By.XPATH, './td[1]').text.strip()
            query = element.find_element(By.XPATH, './td[2]').text.strip()
            reply = element.find_element(By.XPATH, './td[3]').text.strip()

            # Check if the record already exists (unique constraint on bid_no, section, query, reply)
            cur.execute(
                "SELECT 1 FROM representations WHERE bid_no = %s AND section = %s AND query = %s AND reply = %s",
                (bidNo, section, query, reply)
            )
            if not cur.fetchone():
                # Insert representation
                cur.execute(
                    "INSERT INTO representations (bid_no, section, query, reply) VALUES (%s, %s, %s, %s)",
                    (bidNo, section, query, reply)
                )
                # Insert update log
                cur.execute(
                    'INSERT INTO updates (bid_no, status, "timestamp", message, "by") VALUES (%s, %s, %s, %s, %s)',
                    (bidNo, 'new', datetime.now(), 'New Representation added.', 'GeM-BOT')
                )
        cur.close()
    finally:
        WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="representation_modal_ajax"]/div/div/div[4]/a'))).click()
        WebDriverWait(driver, 5).until(EC.invisibility_of_element_located((By.XPATH, '//*[@id="representation_modal_ajax"]')))


def CorrigendumSearch(driver, otherDetailsElement, conn, bidNo):
    try:
        otherDetailsElement.find_element(By.XPATH, './/*[text()="View Corrigendum"]').click()

        # Wait for the corrigendum details container to load
        WebDriverWait(driver, 5).until(EC.visibility_of_element_located((By.XPATH, '//*[@id="myModal5"]')))
        corrEl = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, '//*[@id="atcBody"]/div[1]/div[3]')))
        elements = corrEl.find_elements(By.CLASS_NAME, 'well')
        cur = conn.cursor()
        i = 0
        while i < len(elements):
            element = elements[i]
            modifiedDate = WebDriverWait(element, 5).until(EC.visibility_of_element_located((By.XPATH, './/div[1]'))).text.replace('Modified On:', '').strip()
            modifiedContent = element.find_element(By.XPATH, './/div[2]')

            try:
                # Check if there's a clickable button in the modified content
                button = modifiedContent.find_element(By.TAG_NAME, 'a')

                # Check if corrigendum with this date already exists
                cur.execute(
                    "SELECT 1 FROM corrigendums WHERE bid_no = %s AND modified_on = %s",
                    (bidNo, modifiedDate.strip())
                )
                if not cur.fetchone():
                    downloadCorrFile(button, directory)
                    fileName = moveLatestFile(directory, os.path.join(directory, bidNo))
                    cur.execute(
                        "INSERT INTO corrigendums (bid_no, modified_on, file_name, message) VALUES (%s, %s, %s, %s)",
                        (bidNo, modifiedDate.replace('Modified On: ', '').strip(), fileName, 'New Corrigendum File updated.')
                    )
                    cur.execute(
                        'INSERT INTO updates (bid_no, status, "timestamp", message, "by") VALUES (%s, %s, %s, %s, %s)',
                        (bidNo, 'new', datetime.now(), 'New corrigendum Added.', 'GeM-BOT')
                    )

            except NoSuchElementException:
                # Handle the case where there's no button, and extract additional details
                cur.execute(
                    "SELECT 1 FROM corrigendums WHERE bid_no = %s AND modified_on = %s",
                    (bidNo, modifiedDate.strip())
                )
                if not cur.fetchone():
                    extendedDate = modifiedContent.text
                    openingDate = WebDriverWait(elements[i+1], 5).until(EC.presence_of_element_located((By.XPATH, './/div[2]'))).text
                    cur.execute(
                        "INSERT INTO corrigendums (bid_no, modified_on, opening_date, extended_date) VALUES (%s, %s, %s, %s)",
                        (bidNo, modifiedDate.replace('Modified On: ', '').strip(),
                         openingDate.replace('Bid Opening Date: ', '').strip(),
                         extendedDate.replace('Bid extended to ', '').strip())
                    )
                    cur.execute(
                        'INSERT INTO updates (bid_no, status, "timestamp", message, "by") VALUES (%s, %s, %s, %s, %s)',
                        (bidNo, 'new', datetime.now(), 'Bid Date has been modified.', 'GeM-BOT')
                    )
                # Skip the next element as it has already been processed
                i += 2
            else:
                # If a button exists, proceed to the next element
                i += 1

        cur.close()
    finally:
        WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="myModal5"]/div/div/div[1]/button'))).click()
        WebDriverWait(driver, 5).until(EC.invisibility_of_element_located((By.XPATH, '//*[@id="myModal5"]')))


# ─── Logger Configuration ────────────────────────────────────────────────────

handler = TimedRotatingFileHandler("Gem.log", when="midnight", interval=1, backupCount=7)
logger = logging.getLogger('GeM-Bidding-Data-Log')
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


# ─── Configure ChromeDriver options ──────────────────────────────────────────

chrome_options = Options()
prefs = {
    "download.default_directory": directory,
    "safebrowsing.enabled": False,
    "download.prompt_for_download": False,
    "download.directory_upgrade": True,
}
chrome_options.add_experimental_option("prefs", prefs)
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-software-rasterizer")
chrome_options.add_argument("--disable-accelerated-2d-canvas")
chrome_options.add_argument("--disable-logging")
chrome_options.add_argument("--v=1")
# chrome_options.add_argument("--headless")  # Headless mode (optional for debugging)


logger.info('GeM Data Capture Service started.')

# ─── Connect to PostgreSQL ───────────────────────────────────────────────────
try:
    conn = get_db_connection()
    init_db(conn)
    logger.info("Connected to PostgreSQL and initialized schema.")
    print("Connected to PostgreSQL successfully.")
except Exception as err:
    logger.critical(f"Failed to connect to PostgreSQL: {err}")
    sendCriticalErrorMail("PostgreSQL Server not working.", f"""
This is the GeM Data Fetching service.

The PostgreSQL database is not working. The current date and time is : {datetime.now().strftime("%d %b, %Y, %I:%M:%S %p")}.

Kindly check the database and resolve any issues.
""")
    exit(1)

# ─── Initialize ChromeDriver ────────────────────────────────────────────────
chrome_driver_path = ChromeDriverManager().install()
service = Service(chrome_driver_path)
driver = webdriver.Chrome(service=service, options=chrome_options)

# Ensure internet connection before proceeding
if not checkInternetConnection():
    logger.critical("Please check your internet connection and try again.")
    exit(1)
else:
    logger.info('Internet Connection Verified Successfully.')


# ─── Main Scraping Loop ─────────────────────────────────────────────────────

# Fetch keywords from PostgreSQL
cur = conn.cursor()
cur.execute("SELECT keyword FROM keywords")
search = cur.fetchall()
cur.close()

for entry in search:
    keyword = entry[0]
    # URL to fetch the data from
    driver.get("https://bidplus.gem.gov.in/all-bids")
    # Wait until the body of the page is loaded
    WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    count = 0
    logger.info(f"Starting the search of {keyword}")
    # Search for the keyword present in the database
    driver.find_element(By.ID, "searchBid").send_keys(keyword)
    driver.find_element(By.ID, "searchBidRA").click()

    # Wait until bids are loaded
    page_data = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, '//*[@id="bidCard"]/div[1]/div[1]/span')))
    tender_number_string = page_data.text.split()

    # Dynamically calculate the total number of pages
    pagination_buttons = driver.find_elements(By.XPATH, '//*[@id="light-pagination"]/a')
    number_of_pages = (int(tender_number_string[6]) // 10) + 1
    count = 0

    # Iterate over all pages
    for i in range(number_of_pages):
        numOfPages = len(driver.find_elements(By.XPATH, '//*[@id="bidCard"]/div')) - 3
        for j in range(2, numOfPages + 2):  # Adjust the range as needed

            try:
                # Extract the Bid Number
                bidNo = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, f'//*[@id="bidCard"]/div[{j}]/div[1]/p[1]/a'))
                ).text.replace('/', '-')
                logger.info(f"Bid Number: {bidNo}")

                # Extract start and end dates of the bid
                startDate = driver.find_element(By.XPATH, f'//*[@id="bidCard"]/div[{j}]/div[3]/div/div[3]/div[1]/span').text
                endDate = driver.find_element(By.XPATH, f'//*[@id="bidCard"]/div[{j}]/div[3]/div/div[3]/div[2]/span').text

                # Check if the bid is already in the database
                cur = conn.cursor()
                cur.execute("SELECT start_date, end_date FROM tenders WHERE bid_no = %s", (bidNo,))
                data = cur.fetchone()

                if data:
                    logger.info('Record Already Exists in Database.')
                    # Update existing bid if start/end date has changed
                    if data[0] != startDate or data[1] != endDate:
                        cur.execute(
                            "UPDATE tenders SET start_date = %s, end_date = %s WHERE bid_no = %s",
                            (startDate, endDate, bidNo)
                        )
                else:
                    # Extract items and other data for a new bid
                    items = driver.find_element(By.XPATH, f'//*[@id="bidCard"]/div[{j}]/div[3]/div/div[1]/div[1]')
                    try:
                        content = items.find_elements(By.TAG_NAME, 'a')
                        itemData = driver.find_element(By.XPATH, f'//*[@id="bidCard"]/div[{j}]/div[3]/div/div[1]/div[1]/a').get_attribute('data-content')
                    except:
                        itemData = driver.find_element(By.XPATH, f'//*[@id="bidCard"]/div[{j}]/div[3]/div/div[1]/div[1]').text

                    # ── Relevance Filter ──────────────────────────────────────
                    # Check if the keyword appears as a whole word (not a substring)
                    # e.g. keyword "LAN" matches "LAN cable" but NOT "plan"
                    pattern = r'\b' + re.escape(keyword) + r'\b'
                    is_relevant = bool(re.search(pattern, itemData, re.IGNORECASE))
                    
                    if not is_relevant:
                        logger.info(f'Skipping {bidNo} — keyword "{keyword}" not a whole-word match in items. Downloading bid file only.')
                        
                        # Create folder for the REJECTED tender
                        rejected_base = os.path.join(directory, "Rejected")
                        bid_directory = os.path.join(rejected_base, bidNo.replace('/', '-'))
                        os.makedirs(bid_directory, exist_ok=True)
                        
                        downloadButton = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, f'//*[@id="bidCard"]/div[{j}]/div[1]/p[1]/a')))
                        fileName = downloadButton.get_attribute('href').replace('https://bidplus.gem.gov.in/showbidDocument/', "")
                        
                        try:
                            downloadBidFile(downloadButton, directory, fileName)
                            moveSelectedFile(directory, bid_directory, fileName)
                        except Exception as e:
                            logger.error(f"Failed to download rejected bid file for {bidNo}: {e}")

                        # Save to rejected_tenders for manual review
                        cur.execute(
                            """INSERT INTO rejected_tenders (bid_no, keyword, items, start_date, end_date)
                               VALUES (%s, %s, %s, %s, %s)
                               ON CONFLICT (bid_no, keyword) DO NOTHING""",
                            (bidNo, keyword, itemData, startDate, endDate)
                        )
                        cur.close()
                        continue
                    # ─────────────────────────────────────────────────────────

                    # Extract quantity and department name/address
                    quantity = driver.find_element(By.XPATH, f'//*[@id="bidCard"]/div[{j}]/div[3]/div/div[1]/div[2]').text
                    departmentNameAndAddress = driver.find_element(By.XPATH, f'//*[@id="bidCard"]/div[{j}]/div[3]/div/div[2]/div[2]').text

                    # Create folder for the tender and download the file
                    bid_directory = os.path.join(directory, bidNo.replace('/', '-'))
                    os.makedirs(bid_directory, exist_ok=True)
                    downloadButton = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, f'//*[@id="bidCard"]/div[{j}]/div[1]/p[1]/a')))
                    fileName = downloadButton.get_attribute('href').replace('https://bidplus.gem.gov.in/showbidDocument/', "")

                    downloadBidFile(downloadButton, directory, fileName)
                    moveSelectedFile(directory, bid_directory, fileName)

                    # Insert new tender into PostgreSQL
                    cur.execute(
                        """INSERT INTO tenders (bid_no, start_date, end_date, items, quantity, department_name_and_address, status)
                           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                        (bidNo, startDate, endDate, itemData, quantity, departmentNameAndAddress, 'new')
                    )
                    # Insert initial update log
                    cur.execute(
                        'INSERT INTO updates (bid_no, status, "timestamp", message, "by") VALUES (%s, %s, %s, %s, %s)',
                        (bidNo, 'new', datetime.now(), 'New Bid Inserted.', 'GeM-BOT')
                    )
                    logger.info(f'Data of {bidNo} inserted successfully.')

                cur.close()

                otherDetailsElement = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, f'//*[@id="bidCard"]/div[{j}]/div[1]/p[2]')))
                otherDetailsElement.click()

                WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))

                corrigendumElement = otherDetailsElement.find_elements(By.XPATH, './/*[text()="View Corrigendum"]')
                representationElement = otherDetailsElement.find_elements(By.XPATH, './/*[text()="View Representation"]')

                if not corrigendumElement and not representationElement:
                    pass
                elif corrigendumElement and not representationElement:
                    CorrigendumSearch(driver, otherDetailsElement, conn, bidNo)
                elif not corrigendumElement and representationElement:
                    representationSearch(driver, otherDetailsElement, conn, bidNo)
                elif corrigendumElement and representationElement:
                    CorrigendumSearch(driver, otherDetailsElement, conn, bidNo)
                    representationSearch(driver, otherDetailsElement, conn, bidNo)
                count += 1
            except Exception as e:
                logger.error(f"Error processing bid at index {j}: {e}")
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO bad_tenders (bid_no, page_no, idx, message) VALUES (%s, %s, %s, %s) ON CONFLICT (bid_no) DO NOTHING",
                    (bidNo, i, j, str(e))
                )
                cur.close()

        # Wait for the "Next" button to be clickable and move to the next page
        next_page_button = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Next')]")))
        next_page_button.click()

        # Wait for the next page to load
        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, '//*[@id="bidCard"]/div[1]/div[1]/span')))
    logger.info(f"Total {keyword} insertions: {count}")

# Cleanup
conn.close()
driver.quit()
