# pip install Flask requests beautifulsoup4
from flask import Flask, request, render_template_string
import requests
from bs4 import BeautifulSoup

# 初始化 Flask 應用程式
app = Flask(__name__)

# --- 輔助函式：電子發票兌獎邏輯 ---
def check_invoice_number(num):
    """
    檢查輸入的發票號碼是否中獎。
    此函式會從財政部網站抓取最新中獎號碼。
    """
    try:
        url = 'https://invoice.etax.nat.gov.tw/index.html'
        web = requests.get(url, timeout=10)
        web.raise_for_status()
        web.encoding = 'utf-8'

        soup = BeautifulSoup(web.text, 'html.parser')
        td = soup.select('.container-fluid')[0].select('.etw-tbiggest')

        ns = td[0].getText() # 特別獎
        n1 = td[1].getText() # 特獎
        n2 = [td[2].getText()[-8:], td[3].getText()[-8:], td[4].getText()[-8:]] # 頭獎

        if num == ns:
            return "🎉 恭喜中獎 1000 萬元"
        elif num == n1:
            return "🎉 恭喜中獎 200 萬元"
        else:
            matched = False
            for i in n2:
                if num == i:
                    return "🎉 恭喜中獎 20 萬元"
                    matched = True
                    break
                elif num[-7:] == i[-7:]:
                    return "🎉 恭喜中獎 4 萬元"
                    matched = True
                    break
                elif num[-6:] == i[-6:]:
                    return "🎉 恭喜中獎 1 萬元"
                    matched = True
                    break
                elif num[-5:] == i[-5:]:
                    return "🎉 恭喜中獎 4000 元"
                    matched = True
                    break
                elif num[-4:] == i[-4:]:
                    return "🎉 恭喜中獎 1000 元"
                    matched = True
                    break
                elif num[-3:] == i[-3:]:
                    return "🎉 恭喜中獎 200 元"
                    matched = True
                    break
            if not matched:
                return "😢 很抱歉，沒中獎"
    except requests.exceptions.RequestException as e:
        return f"無法連接至電子發票網站，請檢查網路連線或稍後再試。詳細錯誤: {e}"
    except Exception as e:
        return f"處理發票兌獎時發生錯誤：{e}"

# --- 輔助函式：股票查詢邏輯 ---
def get_stock_details(code):
    """
    查詢單一股票的即時資訊 (名稱、價格、漲跌)。
    """
    try:
        url = f'https://tw.stock.yahoo.com/quote/{code}'
        web = requests.get(url, timeout=10)
        web.raise_for_status()
        soup = BeautifulSoup(web.text, 'html.parser')

        # --- 提取股票名稱（公司名稱 + 股票代碼） ---
        formatted_title = f'【{code}】' # 預設值，以防所有提取失敗

        # 優先從 HTML 的 <title> 標籤中提取完整名稱，這通常最穩定
        html_title_tag = soup.find('title')
        if html_title_tag:
            full_title_text = html_title_tag.get_text().strip()
            # 範例格式: "公司名稱 (股票代碼) - Yahoo奇摩股市"
            parts = full_title_text.split(' - Yahoo')
            if len(parts) > 0:
                extracted_name_from_title = parts[0].strip()
                if f'({code})' in extracted_name_from_title:
                    formatted_title = f'【{extracted_name_from_title}】'
                else:
                    formatted_title = f'【{extracted_name_from_title} ({code})】'

        # 如果從 <title> 標籤未能得到理想結果，則嘗試從 <h1> 標籤獲取
        if formatted_title == f'【{code}】':
            h1_title_tag = soup.select_one('h1.C($c-link-text).Fz(24px).Mend(8px)')
            if not h1_title_tag:
                h1_title_tag = soup.select_one('div.D\\(ib\\).Mend\\(8px\\) > h1')

            if h1_title_tag:
                raw_h1_text = h1_title_tag.get_text().strip()
                if raw_h1_text:
                    if f'({code})' in raw_h1_text or code in raw_h1_text:
                        formatted_title = f'【{raw_h1_text}】'
                    else:
                        formatted_title = f'【{raw_h1_text} ({code})】'

        # 提取股價與漲跌
        price_tag = soup.select_one('.Fz\\(32px\\)')
        change_tag = soup.select_one('.Fz\\(20px\\)')

        price = price_tag.get_text() if price_tag else 'N/A'
        change_value = change_tag.get_text() if change_tag else 'N/A'

        # 判斷漲跌符號（根據 CSS Class）
        s = ''
        if soup.select_one('#main-0-QuoteHeader-Proxy .C\\(\\$c-trend-up\\)'):
            s = '+'
        elif soup.select_one('#main-0-QuoteHeader-Proxy .C\\(\\$c-trend-down\\)'):
            s = '-'

        return f'{formatted_title}：{price} ({s}{change_value})'

    except requests.exceptions.RequestException as e:
        return f'【{code}】查詢失敗：無法連接或網路錯誤。詳細錯誤: {e}'
    except AttributeError: # 處理 select_one 可能返回 None 的情況
        return f'【{code}】查詢失敗：找不到股價資料或網頁結構已改變。'
    except IndexError: # 處理 select 返回空列表的情況
        return f'【{code}】查詢失敗：找不到股價資料或網頁結構已改變。'
    except Exception as e:
        return f'【{code}】查詢失敗：發生未預期錯誤。詳細錯誤: {e}'

# --- 輔助函式：即時匯率查詢邏輯 ---
def get_exchange_rates():
    """
    從台灣銀行CSV檔案抓取即時匯率資訊。
    回傳一個包含各貨幣名稱和現金賣出匯率的列表。
    """
    try:
        url = 'https://rate.bot.com.tw/xrt/flcsv/0/day'  # 台灣銀行即時匯率CSV檔案網址
        rate_response = requests.get(url, timeout=10)   # 發送GET請求
        rate_response.raise_for_status()                # 檢查 HTTP 請求是否成功
        rate_response.encoding = 'utf-8'                # 設定編碼為UTF-8

        rt_text = rate_response.text                    # 取得回應的文字內容
        rts_lines = rt_text.split('\n')                 # 以換行符號分割成列表

        exchange_rate_list = []
        # 從第二行開始讀取，因為第一行通常是標頭
        for line in rts_lines[1:]: # 跳過CSV標題行
            try:
                if not line.strip(): # 跳過空行
                    continue
                a = line.split(',')                     # 以逗號分割成列表
                # 確保a的長度足夠，避免IndexError
                if len(a) > 12:
                    currency_name = a[0].strip() # 貨幣名稱
                    cash_selling_rate = a[12].strip() # 現金賣出匯率
                    exchange_rate_list.append(f'{currency_name} : {cash_selling_rate}')
            except IndexError:
                # 處理行內數據不完整的錯誤
                continue
            except Exception as e:
                # 處理其他行內處理錯誤
                print(f"處理匯率數據時發生錯誤: {e}")
                continue # 繼續處理下一行
        return exchange_rate_list
    except requests.exceptions.RequestException as e:
        return [f"無法連接至台灣銀行匯率網站，請檢查網路連線或稍後再試。詳細錯誤: {e}"]
    except Exception as e:
        return [f"處理匯率查詢時發生錯誤：{e}"]

# --- 首頁路由 ---
@app.route('/')
def home():
    return render_template_string('''
        <!DOCTYPE html>
        <html lang="zh-Hant">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>功能選單</title>
            <script src="https://cdn.tailwindcss.com"></script>
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
            <style>
                body {
                    font-family: 'Inter', sans-serif;
                    background-color: #f0f4f8;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                    padding: 20px;
                    box-sizing: border-box;
                }
                .container {
                    max-width: 400px;
                    width: 100%;
                    background-color: #ffffff;
                    border-radius: 1rem;
                    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
                    padding: 2.5rem;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    gap: 1.5rem;
                }
                .header {
                    color: #4f46e5;
                    text-align: center;
                }
                .nav-list {
                    width: 100%;
                    list-style: none;
                    padding: 0;
                    margin: 0;
                    display: flex;
                    flex-direction: column;
                    gap: 1rem;
                }
                .nav-list li {
                    width: 100%;
                }
                .nav-list a {
                    display: block;
                    padding: 1rem 1.5rem;
                    background-color: #6366f1;
                    color: white;
                    text-align: center;
                    border-radius: 0.75rem;
                    font-size: 1.1rem;
                    font-weight: 600;
                    transition: background-color 0.2s, transform 0.1s;
                    box-shadow: 0 4px 10px rgba(99, 102, 241, 0.3);
                }
                .nav-list a:hover {
                    background-color: #4f46e5;
                    transform: translateY(-2px);
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1 class="text-3xl font-bold">歡迎使用</h1>
                    <p class="text-lg mt-2 text-gray-600">請選擇一個功能</p>
                </div>
                <ul class="nav-list">
                    <li><a href="/invoice">電子發票兌獎</a></li>
                    <li><a href="/stock">多支股票查詢</a></li>
                    <li><a href="/exchange_rate">即時匯率查詢</a></li> <!-- 新增匯率查詢連結 -->
                </ul>
            </div>
        </body>
        </html>
    ''')

# --- 電子發票兌獎路由 ---
@app.route('/invoice', methods=['GET', 'POST'])
def invoice():
    result = ""
    if request.method == 'POST':
        num = request.form['num'].strip()
        result = check_invoice_number(num) # 呼叫輔助函式

    return render_template_string('''
        <!DOCTYPE html>
        <html lang="zh-Hant">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>電子發票兌獎</title>
            <script src="https://cdn.tailwindcss.com"></script>
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
            <style>
                body {
                    font-family: 'Inter', sans-serif;
                    background-color: #f0f4f8;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                    padding: 20px;
                    box-sizing: border-box;
                }
                .container {
                    max-width: 600px;
                    width: 100%;
                    background-color: #ffffff;
                    border-radius: 1rem;
                    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
                    padding: 2.5rem;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    gap: 1.5rem;
                }
                .header {
                    color: #4f46e5;
                    text-align: center;
                }
                form {
                    width: 100%;
                    display: flex;
                    flex-direction: column;
                    gap: 1rem;
                    align-items: center;
                }
                form input[type="text"] {
                    padding: 0.75rem 1rem;
                    border: 2px solid #cbd5e1;
                    border-radius: 0.5rem;
                    font-size: 1rem;
                    width: 100%;
                    max-width: 300px;
                    transition: border-color 0.2s;
                }
                form input[type="text"]:focus {
                    outline: none;
                    border-color: #4f46e5;
                    box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.2);
                }
                form input[type="submit"] {
                    background-color: #22c55e;
                    color: white;
                    padding: 0.8rem 1.5rem;
                    border-radius: 0.75rem;
                    font-size: 1.1rem;
                    font-weight: 600;
                    cursor: pointer;
                    transition: background-color 0.2s, transform 0.1s;
                    border: none;
                    outline: none;
                    box-shadow: 0 5px 15px rgba(34, 197, 94, 0.3);
                }
                form input[type="submit"]:hover {
                    background-color: #16a34a;
                    transform: translateY(-2px);
                }
                .result-display {
                    margin-top: 1.5rem;
                    padding: 1rem;
                    border-radius: 0.75rem;
                    font-size: 1.25rem;
                    font-weight: 600;
                    text-align: center;
                    width: 100%;
                    background-color: #e2e8f0;
                    color: #334155;
                }
                .home-link {
                    margin-top: 1.5rem;
                    color: #4f46e5;
                    text-decoration: none;
                    font-weight: 600;
                    transition: color 0.2s;
                }
                .home-link:hover {
                    color: #3b82f6;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2 class="text-2xl font-bold">電子發票兌獎</h2>
                    <p class="text-gray-600 mt-1">請輸入您的發票號碼進行兌獎</p>
                </div>
                <form method="post">
                    發票號碼：<input type="text" name="num" maxlength="8" placeholder="請輸入8位數字" pattern="\\d{8}" title="請輸入8位數字的發票號碼" required>
                    <input type="submit" value="兌獎">
                </form>
                <p class="result-display">{{ result }}</p>
                <a href="/" class="home-link">回首頁</a>
            </div>
        </body>
        </html>
    ''', result=result)

# --- 多支股票查詢路由 ---
@app.route('/stock', methods=['GET', 'POST'])
def stock():
    results = []
    if request.method == 'POST':
        codes = request.form['codes'].split(',')
        codes = [c.strip() for c in codes if c.strip()]

        for code in codes:
            # 呼叫輔助函式
            stock_info = get_stock_details(code)
            results.append(stock_info)

    return render_template_string('''
        <!DOCTYPE html>
        <html lang="zh-Hant">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>多支股票即時查詢</title>
            <script src="https://cdn.tailwindcss.com"></script>
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
            <style>
                body {
                    font-family: 'Inter', sans-serif;
                    background-color: #f0f4f8;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                    padding: 20px;
                    box-sizing: border-box;
                }
                .container {
                    max-width: 600px;
                    width: 100%;
                    background-color: #ffffff;
                    border-radius: 1rem;
                    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
                    padding: 2.5rem;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    gap: 1.5rem;
                }
                .header {
                    color: #4f46e5;
                    text-align: center;
                }
                form {
                    width: 100%;
                    display: flex;
                    flex-direction: column;
                    gap: 1rem;
                    align-items: center;
                }
                form input[type="text"] {
                    padding: 0.75rem 1rem;
                    border: 2px solid #cbd5e1;
                    border-radius: 0.5rem;
                    font-size: 1rem;
                    width: 100%;
                    max-width: 350px;
                    transition: border-color 0.2s;
                }
                form input[type="text"]:focus {
                    outline: none;
                    border-color: #4f46e5;
                    box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.2);
                }
                form input[type="submit"] {
                    background-color: #22c55e;
                    color: white;
                    padding: 0.8rem 1.5rem;
                    border-radius: 0.75rem;
                    font-size: 1.1rem;
                    font-weight: 600;
                    cursor: pointer;
                    transition: background-color 0.2s, transform 0.1s;
                    border: none;
                    outline: none;
                    box-shadow: 0 5px 15px rgba(34, 197, 94, 0.3);
                }
                form input[type="submit"]:hover {
                    background-color: #16a34a;
                    transform: translateY(-2px);
                }
                .results-section {
                    width: 100%;
                    background-color: #eef2ff;
                    border: 2px solid #a78bfa;
                    border-radius: 0.75rem;
                    padding: 1.5rem;
                    margin-top: 1.5rem;
                    text-align: left;
                }
                .results-section p {
                    font-size: 1rem;
                    color: #4c1d95;
                    margin-bottom: 0.5rem;
                    word-break: break-word;
                }
                .home-link {
                    margin-top: 1.5rem;
                    color: #4f46e5;
                    text-decoration: none;
                    font-weight: 600;
                    transition: color 0.2s;
                }
                .home-link:hover {
                    color: #3b82f6;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2 class="text-2xl font-bold">多支股票即時查詢</h2>
                    <p class="text-gray-600 mt-1">請輸入股票代碼（用逗號分隔）</p>
                </div>
                <form method="post">
                    <label for="codes" class="sr-only">輸入股票代碼（用逗號分隔）</label>
                    <input type="text" name="codes" id="codes" placeholder="例如: 2330, 2454" style="width:100%">
                    <input type="submit" value="查詢">
                </form>
                <hr class="w-full border-t border-gray-300 my-4">
                <div class="results-section">
                    {% if results %}
                        {% for line in results %}
                            <p>{{ line }}</p>
                        {% endfor %}
                    {% else %}
                        <p>輸入股票代碼後，結果將顯示在此。</p>
                    {% endif %}
                </div>
                <a href="/" class="home-link">回首頁</a>
            </div>
        </body>
        </html>
    ''', results=results)

# --- 即時匯率查詢路由 ---
@app.route('/exchange_rate')
def exchange_rate():
    # 呼叫輔助函式獲取匯率數據
    rates = get_exchange_rates()
    return render_template_string('''
        <!DOCTYPE html>
        <html lang="zh-Hant">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>即時匯率查詢</title>
            <script src="https://cdn.tailwindcss.com"></script>
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
            <style>
                body {
                    font-family: 'Inter', sans-serif;
                    background-color: #f0f4f8;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                    padding: 20px;
                    box-sizing: border-box;
                }
                .container {
                    max-width: 600px;
                    width: 100%;
                    background-color: #ffffff;
                    border-radius: 1rem;
                    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
                    padding: 2.5rem;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    gap: 1.5rem;
                }
                .header {
                    color: #4f46e5;
                    text-align: center;
                }
                .rate-list-container {
                    width: 100%;
                    max-height: 400px; /* 限制高度並允許滾動 */
                    overflow-y: auto;
                    background-color: #eef2ff;
                    border: 2px solid #a78bfa;
                    border-radius: 0.75rem;
                    padding: 1.5rem;
                    margin-top: 1.5rem;
                    text-align: left;
                }
                .rate-list-container p {
                    font-size: 1rem;
                    color: #4c1d95;
                    margin-bottom: 0.5rem;
                    word-break: break-word;
                    padding: 0.25rem 0;
                    border-bottom: 1px dotted #d1d5db; /* 增加分隔線 */
                }
                .rate-list-container p:last-child {
                    border-bottom: none; /* 最後一行不要分隔線 */
                }
                .home-link {
                    margin-top: 1.5rem;
                    color: #4f46e5;
                    text-decoration: none;
                    font-weight: 600;
                    transition: color 0.2s;
                }
                .home-link:hover {
                    color: #3b82f6;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2 class="text-2xl font-bold">即時匯率查詢</h2>
                    <p class="text-gray-600 mt-1">台灣銀行即時匯率（現金賣出）</p>
                </div>
                <div class="rate-list-container">
                    {% if rates %}
                        {% for rate_item in rates %}
                            <p>{{ rate_item }}</p>
                        {% endfor %}
                    {% else %}
                        <p>無法載入匯率資料。</p>
                    {% endif %}
                </div>
                <a href="/" class="home-link">回首頁</a>
            </div>
        </body>
        </html>
    ''', rates=rates)


# 如果以主程式執行，則啟動 Flask 伺服器
if __name__ == '__main__':
    # debug=True 會在程式碼修改時自動重載，並提供更詳細的錯誤訊息
    app.run(debug=True)
