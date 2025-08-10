def _generate_css():
    return """
    <style>
        body { 
            font-family: sans-serif; background-color: #2e2e2e; color: #e0e0e0; 
            margin: 0; padding: 20px; overflow-x: hidden;
        }
        .container { 
            display: flex; flex-direction: column; align-items: center; 
            width: 100%;
        }
        .lifelines { 
            display: flex; justify-content: space-around; width: 100%; 
            padding: 20px 0; position: relative;
        }
        .lifeline { 
            display: flex; flex-direction: column; align-items: center; 
            width: 100px;
        }
        .lifeline-box {
            background-color: #4a4a4a; border: 1px solid #666; border-radius: 8px;
            padding: 10px; font-weight: bold; margin-bottom: 10px;
        }
        .lifeline-line {
            width: 2px; background-color: #666; flex-grow: 1;
        }
        .sequence {
            position: absolute; top: 100px; left: 0; right: 0;
            display: flex; flex-direction: column; gap: 40px;
            padding: 0 10%;
        }
        .message {
            position: relative; width: 100%;
        }
        .message-line {
            position: absolute; height: 2px;
            background-color: #e0e0e0;
        }
        .message-arrow {
            position: absolute; top: -7px; width: 0; height: 0;
            border-top: 8px solid transparent;
            border-bottom: 8px solid transparent;
        }
        .message-label {
            position: absolute; top: -25px;
            background-color: #2e2e2e; padding: 0 5px;
            font-size: 14px; white-space: nowrap;
        }
        .send .message-line { left: 25%; width: 50%; background-color: #007acc; }
        .send .message-arrow { left: 75%; border-left: 16px solid #007acc; }
        .send .message-label { left: 50%; transform: translateX(-50%); color: #007acc; }
        
        .expect .message-line { left: 25%; width: 50%; background-color: #2a9d8f; }
        .expect .message-arrow { left: 25%; transform: translateX(-100%); border-right: 16px solid #2a9d8f; }
        .expect .message-label { left: 50%; transform: translateX(-50%); color: #2a9d8f; }
    </style>
    """

def _generate_sequence_html(steps):
    html = ""
    for step in steps:
        action = step.get('action')
        if action in ['send', 'expect']:
            message = step.get('message', 'N/A')
            html += f"""
            <div class="message {action}">
                <div class="message-line"></div>
                <div class="message-arrow"></div>
                <div class="message-label">{message}</div>
            </div>
            """
    return html

def generate_sequence_html(scenario_data):
    """Generates a full HTML page for the scenario sequence diagram."""
    steps_html = _generate_sequence_html(scenario_data.get('steps', []))
    num_steps = len([s for s in scenario_data.get('steps', []) if s.get('action') in ['send', 'expect']])
    lifeline_height = max(200, num_steps * 80) # Calculate dynamic height

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        {_generate_css()}
    </head>
    <body>
        <div class="container">
            <div class="lifelines" style="height: {lifeline_height}px;">
                <div class="lifeline">
                    <div class="lifeline-box">Host</div>
                    <div class="lifeline-line"></div>
                </div>
                <div class="lifeline">
                    <div class="lifeline-box">Equipment</div>
                    <div class="lifeline-line"></div>
                </div>
                <div class="sequence">
                    {steps_html}
                </div>
            </div>
        </div>
    </body>
    </html>
    """
