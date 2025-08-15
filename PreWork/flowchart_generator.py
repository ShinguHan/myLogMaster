# This module converts a scenario dictionary into a self-contained HTML flowchart.

def _generate_css():
    return """
    <style>
        body { font-family: sans-serif; background-color: #2e2e2e; color: #e0e0e0; padding: 20px; }
        .flowchart { display: flex; flex-direction: column; align-items: center; gap: 10px; }
        .step {
            background-color: #4a4a4a; border: 1px solid #666; border-radius: 8px;
            padding: 10px 15px; min-width: 200px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.5);
        }
        .step.send { border-left: 5px solid #007acc; }
        .step.expect { border-left: 5px solid #2a9d8f; }
        .step.log { border-left: 5px solid #e9c46a; }
        .connector { color: #888; font-size: 20px; }
        .block {
            border: 1px dashed #888; border-radius: 10px; padding: 15px;
            margin-top: 10px; background-color: #383838;
            display: flex; flex-direction: column; align-items: center; gap: 10px;
        }
        .block-title { font-weight: bold; color: #ccc; margin-bottom: 10px; }
        .if-container { display: flex; gap: 20px; align-items: flex-start; }
        .if-branch { display: flex; flex-direction: column; align-items: center; gap: 10px; }
    </style>
    """

def _generate_steps_html(steps):
    html = ""
    for i, step in enumerate(steps):
        action = step.get('action', 'unknown')
        
        if action in ['send', 'expect', 'log']:
            details = step.get('message', '')
            html += f'<div class="step {action}"><strong>{action.upper()}</strong>: {details}</div>'
        elif action == 'loop':
            count = step.get('count', 'N')
            html += f'<div class="block loop">'
            html += f'<div class="block-title">LOOP ({count} times)</div>'
            html += _generate_steps_html(step.get('steps', []))
            html += f'</div>'
        elif action == 'if':
            condition = step.get('condition', 'true')
            html += f'<div class="block if">'
            html += f'<div class="block-title">IF ({condition})</div>'
            html += '<div class="if-container">'
            # "Then" branch
            html += '<div class="if-branch">'
            html += '<div class="block-title" style="color: #2a9d8f;">THEN</div>'
            html += _generate_steps_html(step.get('then', []))
            html += '</div>'
            # "Else" branch
            html += '<div class="if-branch">'
            html += '<div class="block-title" style="color: #e63946;">ELSE</div>'
            html += _generate_steps_html(step.get('else', []))
            html += '</div>'
            html += '</div></div>'
        
        # Add a connector if it's not the last step
        if i < len(steps) - 1:
            html += '<div class="connector">&darr;</div>'
            
    return html

def generate_flowchart_html(scenario_data):
    """Generates a full HTML page for the scenario flowchart."""
    scenario_name = scenario_data.get('name', 'Untitled Scenario')
    steps_html = _generate_steps_html(scenario_data.get('steps', []))
    
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        {_generate_css()}
    </head>
    <body>
        <div class="flowchart">
            <div class="step" style="background-color: #003f5c;"><strong>START:</strong> {scenario_name}</div>
            <div class="connector">&darr;</div>
            {steps_html}
            <div class="connector">&darr;</div>
            <div class="step" style="background-color: #581845;"><strong>END</strong></div>
        </div>
    </body>
    </html>
    """
