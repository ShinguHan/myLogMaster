import database_handler

def generate_dashboard_html():
    """Queries the database and generates a self-contained HTML dashboard."""
    
    pass_fail_data = database_handler.get_pass_fail_ratio()
    daily_counts = database_handler.get_daily_run_counts()

    # Prepare data for Chart.js
    pass_fail_labels = [row[0] for row in pass_fail_data]
    pass_fail_values = [row[1] for row in pass_fail_data]
    
    daily_labels = [row[0] for row in daily_counts]
    daily_values = [row[1] for row in daily_counts]

    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            body {{ font-family: sans-serif; background-color: #2e2e2e; color: #e0e0e0; padding: 20px; }}
            h1 {{ text-align: center; color: #fff; }}
            .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; }}
            .chart-container {{ background-color: #383838; padding: 20px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.5); }}
            h2 {{ margin-top: 0; border-bottom: 1px solid #555; padding-bottom: 10px; }}
        </style>
    </head>
    <body>
        <h1>Test Results: Trend Analysis</h1>
        <div class="grid">
            <div class="chart-container">
                <h2>Overall Pass/Fail Ratio</h2>
                <canvas id="passFailChart"></canvas>
            </div>
            <div class="chart-container">
                <h2>Daily Test Volume</h2>
                <canvas id="dailyRunsChart"></canvas>
            </div>
        </div>
        <script>
            const passFailCtx = document.getElementById('passFailChart').getContext('2d');
            new Chart(passFailCtx, {{
                type: 'pie',
                data: {{
                    labels: {pass_fail_labels},
                    datasets: [{{
                        label: 'Test Results',
                        data: {pass_fail_values},
                        backgroundColor: ['#2a9d8f', '#e63946'],
                        hoverOffset: 4
                    }}]
                }}
            }});

            const dailyRunsCtx = document.getElementById('dailyRunsChart').getContext('2d');
            new Chart(dailyRunsCtx, {{
                type: 'line',
                data: {{
                    labels: {daily_labels},
                    datasets: [{{
                        label: 'Test Runs',
                        data: {daily_values},
                        borderColor: '#007acc',
                        backgroundColor: 'rgba(0, 122, 204, 0.2)',
                        fill: true,
                        tension: 0.1
                    }}]
                }}
            }});
        </script>
    </body>
    </html>
    """
    return html
