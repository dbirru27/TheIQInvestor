import json
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime

def plot_chart(ticker, dates_str, prices):
    dates = [datetime.strptime(d, '%Y-%m-%d') for d in dates_str]
    
    plt.figure(figsize=(10, 6))
    plt.plot(dates, prices, color='#4facfe', linewidth=2)
    plt.fill_between(dates, prices, color='#4facfe', alpha=0.1)
    
    plt.title(f"{ticker} - 6 Month Trend", fontsize=16, color='white')
    plt.grid(True, linestyle='--', alpha=0.3, color='#334155')
    
    # Dark mode theme
    plt.gcf().set_facecolor('#0f172a')
    plt.gca().set_facecolor('#1e293b')
    plt.gca().spines['bottom'].set_color('#94a3b8')
    plt.gca().spines['top'].set_color('#94a3b8') 
    plt.gca().spines['right'].set_color('#94a3b8')
    plt.gca().spines['left'].set_color('#94a3b8')
    plt.tick_params(colors='white')
    
    # Format dates
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
    
    filename = f"{ticker}_chart.png"
    plt.savefig(filename, facecolor='#0f172a', bbox_inches='tight')
    plt.close()
    return filename

if __name__ == "__main__":
    with open("charts_data.json", "r") as f:
        data = json.load(f)
    
    for ticker, values in data.items():
        print(f"Plotting {ticker}...")
        plot_chart(ticker, values['dates'], values['prices'])
    print("Done!")
