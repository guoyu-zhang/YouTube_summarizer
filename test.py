import os
import requests
from dotenv import load_dotenv

# Load the .env file to get your proxy URL
load_dotenv()
proxy_url = os.environ.get("PROXY_URL")

if not proxy_url:
    print("🛑 PROXY_URL not found in .env file.")
else:
    print(f"Proxy found: {proxy_url}")
    proxies = {
        "http": proxy_url,
        "https": proxy_url,
    }

    try:
        # Use icanhazip.com, which returns plain text
        ip_check_url = "https://icanhazip.com"

        print("\nConnecting without proxy...")
        response_no_proxy = requests.get(ip_check_url, timeout=10)
        # .strip() removes any extra whitespace or newlines
        ip_no_proxy = response_no_proxy.text.strip()
        print(f"✅ Your IP: {ip_no_proxy}")

        print("\nConnecting WITH proxy...")
        response_with_proxy = requests.get(ip_check_url, proxies=proxies, timeout=15)
        ip_with_proxy = response_with_proxy.text.strip()
        print(f"✅ Proxy's IP: {ip_with_proxy}")

        if ip_no_proxy != ip_with_proxy:
            print("\n🎉 Success! The proxy is working correctly.")
        else:
            print("\n⚠️ Warning: The IP address did not change. The proxy may not be working.")

    except requests.RequestException as e:
        print(f"\n❌ Error connecting with proxy: {e}")