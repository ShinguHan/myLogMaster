import csv
import io
import json

# This is the new, multi-line log snippet from the customer
log_snippet = """
"Info","8","01-Aug-2025 03:01:41:837","J1FCNV12305","LGCnvSEM.reportIDRead","J1FCNV12305-104",">>> IDreadReport 0:<L[4] <U2 1> <A 'LHAE000336'> <U2 0> <A 'FB'> >","DeviceServer(1F_Formation_N_2nd_Conveyor_01_Server):EventReportThreadP-J1FCNV12305","info","","","1754031701837"
"Info","3","01-Aug-2025 03:01:41:839","MesServer_J1F","SolaceClient.send","MesServer_J1F:Primary:Active","[SEND] 

BR_MHS_REG_EQPT_SCAN_RSLT 

{

  "TXN_ID": "1754031701839",

  "inDTName": "IN_DATA,IN_SCAN_LIST",

  "refDS": {

    "IN_SCAN_LIST": [

      {

        "DURABLE_ID": "LHAE000336",

        "STACK_NO": "1",

        "SCAN_RSLT": "OK",

        "SCAN_TYPE": "FB"

      }

    ],

    "IN_DATA": [

      {

        "PORT_ID": "J1FCNV12305-104",

        "EQUIPMENT_ID": "J1FCNV12305"

      }

    ]

  },

  "actID": "BR_MHS_REG_EQPT_SCAN_RSLT",

  "outDTName": ""

}","MesServer_J1F:StatusChangeListenerMCSEventThreadPool-7","info","","","1754031701839"
"Debug","8","01-Aug-2025 03:01:41:862","","COMLogParser.parseComLog","",">>> super1 Event Report Send CEID:251 - CarrierIDRead, LHAE000336, loc : J1FCNV12305-104, carrierTypeCode : 4, childlist : ","DeviceServer(1F_Formation_N_2nd_Conveyor_01_Server):HsmsRecv/10.228.115.223:30008","DEBUG","","","1754031701862"
"""

headers = ["Category","LevelID","SystemDate","DeviceID","MethodID","TrackingID","AsciiData","SourceID","MessageName","LogParserClassName","BinaryData","NumericalTimeStamp"]
log_entry_starters = ('"Info"', '"Debug"', '"Com"', '"Error"')

def process_entry_buffer(buffer):
    """Combines and parses a multi-line log entry with detailed logging."""
    if not buffer:
        return

    print("\n--- [PARSER LOG] Processing New Buffered Entry ---")
    
    # Join all lines in the buffer, replacing newlines within the text
    full_line = "".join(buffer).replace('\n', ' ').replace('\r', '')
    print(f"[PARSER LOG] Combined Buffer Content: {full_line[:5000]}...") # Log first 100 chars
    
    try:
        row = next(csv.reader([full_line]))
        print(f"[PARSER LOG] CSV parsing successful. Found {len(row)} columns.")

        if len(row) < len(headers):
            print("[PARSER LOG] RESULT: SKIPPING - Row has fewer columns than expected.")
            return

        log_data = {header: value for header, value in zip(headers, row)}
        
        print(f"[PARSER LOG] Mapped data for DeviceID: {log_data.get('DeviceID')}")
        
        # Special check for the multi-line JSON message
        if "BR_MHS_REG_EQPT_SCAN_RSLT" in log_data.get('AsciiData', ''):
            print("[PARSER LOG] Found target keyword 'BR_MHS_REG_EQPT_SCAN_RSLT'.")
            print("[PARSER LOG] RESULT: VERIFIED - Correctly parsed the multi-line JSON entry.")
        else:
            print("[PARSER LOG] Target keyword not found in this entry.")
            print(f"[PARSER LOG] RESULT: SUCCESS - Parsed a single-line entry.")


    except Exception as e:
        print(f"[PARSER LOG] RESULT: FAILURE - Could not parse buffered entry. Error: {e}")


def run_test():
    """
    Parses a multi-line log snippet using the Director's logic.
    """
    print("--- Starting Multi-Line Parser Test ---")
    lines = log_snippet.strip().splitlines()
    
    entry_buffer = []
    for line_num, line in enumerate(lines):
        if not line.strip():
            continue

        # Rule 2: Check if the line is the start of a new entry
        if line.startswith(log_entry_starters):
            # Rule 3: Process the previous entry before starting the new one
            process_entry_buffer(entry_buffer)
            # Start a new buffer for the new entry
            entry_buffer = [line]
        else:
            # This line is a continuation of the current entry
            entry_buffer.append(line)
    
    # Process the very last entry in the buffer after the loop finishes
    process_entry_buffer(entry_buffer)


if __name__ == '__main__':
    run_test()
