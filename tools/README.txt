NSE requires MultiMonitorTool.exe (by NirSoft) to save and restore your
7-monitor layout automatically when RESTORE is pressed.

NSE does not bundle this tool. Download it yourself from the official
NirSoft site and place MultiMonitorTool.exe directly in this "tools"
folder (next to this README), matching your system architecture
(32-bit or 64-bit build):

    https://www.nirsoft.net/utils/multi_monitor_tool.html

Verify the download (e.g. check it's signed / scan it) before running it,
same as any executable from a third party.

Once it's in place:
  1. Arrange your 7 monitors the way you want them (Settings > Display).
  2. Launch NSE and click "SAVE LAYOUT" once to capture that arrangement.
  3. From then on, RESTORE will re-enable the secondary GPU, extend the
     displays, and reapply the saved layout automatically.

If MultiMonitorTool.exe is missing, ENGAGE/RESTORE still work (GPU
disable/enable + display switch), you'll just need to reposition monitors
by hand after RESTORE.
