import wx
import wx.html2 as html2
import wx.grid as gridlib
import cgi
import sys
import numpy as np
import math
import matplotlib.pyplot as plt
import json
#plt.use('WXAgg')

from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
from matplotlib.backends.backend_wx import NavigationToolbar2Wx
from matplotlib.figure import Figure

class TabPanel(wx.Panel):
  def __init__(self, parent, topLevelPanel, profile_points, profile_filename, event_descriptors):
    wx.Panel.__init__(self, parent)
    self.event_descriptors=event_descriptors
    self.profile_points=profile_points
    self.profile_shortfilename=profile_filename.split("/")[-1]
    self.profile_filecontents = self.getProfileContents(profile_filename)
    self.timeProfiled=False
    self.parseTimePoints()
    self.collection_names=self.generateCollectionNames()

    self.current_collection_events = {}
    self.ordered_collection_keys = []

    self.parseProfileGeneralInfo()

    self.topLevelPanel=topLevelPanel
    self.eventsGrid = gridlib.Grid(self, size=(400,600))
    self.eventsGrid.CreateGrid(self.number_events, 3 if self.timeProfiled else 2)
    self.eventsGrid.SetColLabelValue(0, "Hardware event name")
    self.eventsGrid.SetColLabelValue(1, "Counts")
    if self.timeProfiled: self.eventsGrid.SetColLabelValue(2, "Std Dev")

    self.Bind(wx.grid.EVT_GRID_CELL_RIGHT_CLICK, self.RightClickOnRawValuesGrid, self.eventsGrid)

    self.derivedGrid = gridlib.Grid(self)
    self.derivedGrid.CreateGrid(14, 3 if self.timeProfiled else 2)
    self.derivedGrid.SetColLabelValue(0, "Metric")
    self.derivedGrid.SetColLabelValue(1, "Quantity")
    if self.timeProfiled: self.derivedGrid.SetColLabelValue(2, "Std Dev")

    self.Bind(wx.grid.EVT_GRID_CELL_RIGHT_CLICK, self.RightClickOnDerivedValuesGrid, self.derivedGrid)

    self.profile_collection_chooser = wx.ComboBox(self, choices=self.collection_names)
    self.profile_collection_chooser.SetSelection(0)
    self.Bind(wx.EVT_COMBOBOX, self.comboBoxChange, self.profile_collection_chooser)

    sizer = wx.BoxSizer(wx.VERTICAL)
    sizer.Add(self.profile_collection_chooser, 0, wx.EXPAND | wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, 2)
    sizer.Add(self.eventsGrid, 2, wx.EXPAND | wx.ALIGN_CENTER_HORIZONTAL | wx.ALL)
    sizer.Add(self.derivedGrid, 2, wx.EXPAND | wx.ALIGN_CENTER_HORIZONTAL | wx.ALL)
    self.SetSizer(sizer)

  def parseTimePoints(self):
    self.tp_collections={}
    counting_tps=False
    activeCollection = False
    num_tp_count=0
    collection_id=0
    cid=0
    self.tp_collection_keys={}
    collection_events={}
    collection_index={}
    num_events=0
    for line in self.profile_filecontents.split("\n"):
      if "Total number events tracked: " in line:
        num_events=int(line.split(": ")[1])
      elif "Collection:" in line:
        activeCollection = True
        cid = int(line.split("Collection:")[1].strip())
        self.tp_collection_keys[cid] = []
      elif activeCollection and "Activations: " in line:
        collection_events[cid]=math.ceil(int(line.split(": ")[1]))# / 100)
        collection_index[cid]=0
      elif activeCollection and "=" in line:
        components = line.split("=")
        self.tp_collection_keys[cid].append(components[0].strip())

    for key in collection_events:
      self.tp_collections[key] = np.zeros(shape=[num_events, collection_events[key]],
                                                    dtype=np.int64)


    for line in self.profile_filecontents.split("\n"):
      if "TP: " in line:
        if not self.timeProfiled:
          self.timeProfiled=True
        tokens=line.split(" ")
        collection_id=int(tokens[1])
        num_tp_count=int(tokens[3])
        counting_tps=True
      elif counting_tps:
        values=line.split(",")
        evt_index=0
        tp_index=collection_index[collection_id]
        for value in values:
          self.tp_collections[collection_id][evt_index][tp_index]+=np.int64(value)
          evt_index+=1
        num_tp_count-=1
        collection_index[collection_id]+=1
        if (num_tp_count == 0): counting_tps=False

  def RightClickOnDerivedValuesGrid(self, event):
    rows = self.derivedGrid.GetSelectedRows()
    if (len(rows) > 0):
      row=rows[0]
      menu = wx.Menu()

      v=menu.Append(0, "Time profile")
      self.Bind(wx.EVT_MENU, self.MenuSelectionDerivedValues, v)

      v = menu.Append(1, "Plot distributions")
      self.Bind(wx.EVT_MENU, self.MenuSelectionDerivedValuesDistributions, v)

      pos = event.GetPosition()
      #pos = self.topLevelPanel.parent.ScreenToClient(pos)

      self.PopupMenu(menu, pos)
      menu.Destroy()  # destroy to avoid mem leak

  def MenuSelectionDerivedValuesDistributions(self, event):
    row = self.derivedGrid.GetSelectedRows()[0]
    collection_idx = self.profile_collection_chooser.GetSelection()
    data=self.getDerivedTimeSeriesValues(row, collection_idx)

    OtherFrame(self.getDerivedTimeSeriesName(row) + " (" + self.profile_shortfilename + ")",
               np.histogram(data, bins=10))

  def getDerivedTimeSeriesValues(self, row, collection_idx):
    if row >= 0 and row <= 13:
      cycles_location_index = self.ordered_collection_keys.index("CPU_CLK_THREAD_UNHALTED:THREAD_P")
      num_time_points = len(self.tp_collections[collection_idx][0])
      data = np.zeros(shape=[num_time_points], dtype=np.float64)
      if row == 0 or row == 1:
        for i in range(12, 19):
          for j in range(0, num_time_points):
            data[j] += self.tp_collections[collection_idx][i][j]
        if row == 1:
          for j in range(0, num_time_points):
            val = self.tp_collections[collection_idx][cycles_location_index][j]
            if (val > 0):
              data[j] /= val
            else:
              data[j] = 0
      elif (row >= 2 and row <= 5) or (row >= 9 and row <= 12):
        cycles_location_index = self.ordered_collection_keys.index("CPU_CLK_THREAD_UNHALTED:THREAD_P")
        if row == 2:
          accessidx = self.ordered_collection_keys.index("RESOURCE_STALLS:ALL")
        elif row == 3:
          accessidx = self.ordered_collection_keys.index("RESOURCE_STALLS:RS")
        elif row == 4:
          accessidx = self.ordered_collection_keys.index("RESOURCE_STALLS:SB")
        elif row == 5:
          accessidx = self.ordered_collection_keys.index("RESOURCE_STALLS:ROB")
        elif row == 9:
          accessidx = self.ordered_collection_keys.index("CYCLE_ACTIVITY:STALLS_TOTAL")
        elif row == 10:
          accessidx = self.ordered_collection_keys.index("CYCLE_ACTIVITY:STALLS_L2_PENDING")
        elif row == 11:
          accessidx = self.ordered_collection_keys.index("CYCLE_ACTIVITY:STALLS_L1D_PENDING")
        elif row == 12:
          accessidx = self.ordered_collection_keys.index("CYCLE_ACTIVITY:STALLS_LDM_PENDING")
        for j in range(0, num_time_points):
          val = self.tp_collections[collection_idx][cycles_location_index][j]
          stall = float(self.tp_collections[collection_idx][accessidx][j])
          if val > 0 and stall > 0.0:
            calc = (stall / val) * 100
            data[j] = calc
          else:
            data[j] = 0
      elif row == 6:
        for j in range(0, num_time_points):
          miss_branches = \
          self.tp_collections[collection_idx][self.ordered_collection_keys.index("BR_MISP_RETIRED:ALL_BRANCHES")][j]
          all_branches = float(
            self.tp_collections[collection_idx][self.ordered_collection_keys.index("BR_INST_RETIRED:ALL_BRANCHES")][j])
          if all_branches > 0:
            data[j] = (miss_branches / all_branches) * 100
      elif row == 7:
        for j in range(0, num_time_points):
          cycles_location_index = self.ordered_collection_keys.index("CPU_CLK_THREAD_UNHALTED:THREAD_P")
          total_num_cycles = self.tp_collections[collection_idx][cycles_location_index][j]
          instr_retired = float(
            self.tp_collections[collection_idx][self.ordered_collection_keys.index("INST_RETIRED:ANY_P")][j])
          if instr_retired > 0:
            data[j] = total_num_cycles / instr_retired
      elif row == 8:
        for j in range(0, num_time_points):
          cache_miss = self.tp_collections[collection_idx][self.ordered_collection_keys.index("LONGEST_LAT_CACHE:MISS")][
            j]
          cache_reference = float(
            self.tp_collections[collection_idx][self.ordered_collection_keys.index("LONGEST_LAT_CACHE:REFERENCE")][j])
          if cache_reference > 0:
            data[j] = (cache_miss / cache_reference) * 100
      elif row == 13:
        for j in range(0, num_time_points):
          clock = float(
            self.tp_collections[collection_idx][self.ordered_collection_keys.index("CPU_CLK_THREAD_UNHALTED:REF_XCLK")][
              j])
          if (clock > 0):
            data[j] = clock / 100000000

    return data

  def getDerivedTimeSeriesName(self, row):
    title_names=["Useful cycles", "Cycle utilisation", "% Cycles stalled", "% RS Cycles stalled", "% SB Cycles stalled",
                 "% RoB Cycles stalled", "% branch misspredict", "CPI", "% long misses", "% total execution stalls",
                 "% execution stalls L2", "% execution stalls L1", "% execution stall on memory", "Execution time"]
    return title_names[row]

  def MenuSelectionDerivedValues(self, event):
    row = self.derivedGrid.GetSelectedRows()[0]
    collection_idx = self.profile_collection_chooser.GetSelection()

    OtherFrame(self.getDerivedTimeSeriesName(row)+" ("+self.profile_shortfilename+")", self.getDerivedTimeSeriesValues(row, collection_idx))

  def RightClickOnRawValuesGrid(self, event):
    rows = self.eventsGrid.GetSelectedRows()
    if (len(rows) > 0):
      row=rows[0]
      menu = wx.Menu()

      v=menu.Append(0, "Time profile")
      self.Bind(wx.EVT_MENU, self.MenuSelectionRawValues, v)
      v = menu.Append(1, "Plot distributions")
      self.Bind(wx.EVT_MENU, self.MenuSelectionRawValuesDistributions, v)
      v = menu.Append(2, "Information")
      self.Bind(wx.EVT_MENU, self.MenuSelectionRawValuesInfo, v)

      pos = event.GetPosition()
     # pos = wx.GetMousePosition()# self.topLevelPanel.parent.ScreenToClient(pos)

      self.PopupMenu(menu, pos)
      menu.Destroy()  # destroy to avoid mem leak

  def MenuSelectionRawValuesInfo(self, event):
    row = self.eventsGrid.GetSelectedRows()[0]
    keys=self.eventsGrid.GetCellValue(row, 0).split(" (")

    access_key=keys[0]+"."+keys[1].replace(")", "")

    msg = wx.MessageDialog(self, self.event_descriptors[access_key]["PublicDescription"], access_key,
                           wx.OK | wx.ICON_INFORMATION)
    msg.ShowModal()
    msg.Destroy()
    pass

  def MenuSelectionRawValuesDistributions(self, event):
    row = self.eventsGrid.GetSelectedRows()[0]
    evt_idx = self.profile_collection_chooser.GetSelection()

    OtherFrame(self.tp_collection_keys[evt_idx][row] + " (" + self.profile_shortfilename + ")", np.histogram(self.tp_collections[evt_idx][row], bins=10))

  def MenuSelectionRawValues(self, event):
    row = self.eventsGrid.GetSelectedRows()[0]
    evt_idx=self.profile_collection_chooser.GetSelection()
    OtherFrame(self.tp_collection_keys[evt_idx][row] + " (" + self.profile_shortfilename + ")", self.tp_collections[evt_idx][row])

  def generateCollectionNames(self):
    collection_names = []
    collection_count = 0

    for line in self.profile_filecontents.split("\n"):
      if "Line number:" in line:
        line_num = int(line.split(":")[1].strip())
        collection_names.append(
          "Collection " + str(collection_count) + " between lines " + str(self.profile_points[line_num]) + " and " + str(
            line_num))
        collection_count += 1

    return collection_names

  def getProfileContents(self, profile_filename):
    contents = ""
    file = open(profile_filename, "r")
    for line in file:
      contents += line
    file.close()
    return contents

  def parseProfileGeneralInfo(self):
    self.number_events=0
    for line in self.profile_filecontents.split("\n"):
      if "Total number events tracked:" in line:
        self.number_events=int(line.split("Total number events tracked:")[1].strip())

  def parseProfileReportForCollection(self):
    selectedProfile = self.profile_collection_chooser.GetSelection()
    activeCollection = False
    self.current_collection_events.clear()
    self.ordered_collection_keys.clear()
    for line in self.profile_filecontents.split("\n"):
      if "Collection:" in line:
        if (activeCollection):
          break
        else:
          cid=int(line.split("Collection:")[1].strip())
          if (cid == selectedProfile):
            activeCollection=True
      if activeCollection and "=" in line:
        components = line.split("=")
        self.current_collection_events[components[0].strip()] = int(components[1].strip())
        self.ordered_collection_keys.append(components[0].strip())

  def updateProfilingReport(self):
    row_loc=0
    collection_idx = self.profile_collection_chooser.GetSelection()
    for key in self.ordered_collection_keys:
        value=self.current_collection_events[key]
        event_name_components=key.split(":")
        event_name=event_name_components[0].strip()+" ("+event_name_components[1].strip()+")"
        self.eventsGrid.SetCellValue(row_loc, 0,event_name)
        self.eventsGrid.SetCellValue(row_loc, 1, "{:,}".format(value))
        if self.timeProfiled:
          cycles_location_index=self.ordered_collection_keys.index(key)
          self.eventsGrid.SetCellValue(row_loc, 2, "{:,}".format(round(np.std(self.tp_collections[collection_idx][cycles_location_index]),1)))
        row_loc+=1
    self.eventsGrid.AutoSizeColumns(True)

  def updateMetrics(self):
    collection_idx = self.profile_collection_chooser.GetSelection()
    self.derivedGrid.SetCellValue(0, 0, "Useful cycles")
    total_useful_cycles=(self.current_collection_events["UOPS_EXECUTED_PORT:PORT_0"]+
                                  self.current_collection_events["UOPS_EXECUTED_PORT:PORT_1"]+
                                  self.current_collection_events["UOPS_EXECUTED_PORT:PORT_2"]+
                                  self.current_collection_events["UOPS_EXECUTED_PORT:PORT_3"]+
                                  self.current_collection_events["UOPS_EXECUTED_PORT:PORT_4"]+
                                  self.current_collection_events["UOPS_EXECUTED_PORT:PORT_5"]+
                                  self.current_collection_events["UOPS_EXECUTED_PORT:PORT_6"]+
                                  self.current_collection_events["UOPS_EXECUTED_PORT:PORT_7"])
    self.derivedGrid.SetCellValue(0, 1, "{:,}".format(total_useful_cycles))
    if self.timeProfiled: self.derivedGrid.SetCellValue(0, 2,
                                  "{:,}".format(round(np.std(self.getDerivedTimeSeriesValues(0, collection_idx)), 1)))

    total_num_cycles=self.current_collection_events["CPU_CLK_THREAD_UNHALTED:THREAD_P"]

    self.derivedGrid.SetCellValue(1, 0, "Cycle utilisation")
    if total_num_cycles > 0:
      value_str=str(round(float(total_useful_cycles) / total_num_cycles, 5))
    else:
      value_str="-"
    self.derivedGrid.SetCellValue(1, 1, value_str)
    if self.timeProfiled: self.derivedGrid.SetCellValue(1, 2, "{:,}".format(round(np.std(self.getDerivedTimeSeriesValues(1, collection_idx)), 1)))

    self.derivedGrid.SetCellValue(2, 0, "% Cycles stalled")
    if total_num_cycles > 0:
      value_str=str(round((float(self.current_collection_events["RESOURCE_STALLS:ALL"]) / total_num_cycles)*100, 5))
    else:
      value_str="-"

    self.derivedGrid.SetCellValue(2, 1, value_str)
    if self.timeProfiled: self.derivedGrid.SetCellValue(2, 2,
                                  "{:,}".format(round(np.std(self.getDerivedTimeSeriesValues(2, collection_idx)), 5)))

    self.derivedGrid.SetCellValue(3, 0, "% RS Cycles stalled")
    if total_num_cycles > 0:
      value_str =str(round((float(self.current_collection_events["RESOURCE_STALLS:RS"]) / total_num_cycles)*100, 5))
    else:
      value_str = "-"
    self.derivedGrid.SetCellValue(3, 1, value_str)
    if self.timeProfiled: self.derivedGrid.SetCellValue(3, 2,
                                  "{:,}".format(round(np.std(self.getDerivedTimeSeriesValues(3, collection_idx)), 5)))

    self.derivedGrid.SetCellValue(4, 0, "% SB Cycles stalled")
    if total_num_cycles > 0:
      value_str =str(round((float(self.current_collection_events["RESOURCE_STALLS:SB"]) / total_num_cycles)*100, 5))
    else:
      value_str = "-"

    self.derivedGrid.SetCellValue(4, 1, value_str)
    if self.timeProfiled: self.derivedGrid.SetCellValue(4, 2,
                                  "{:,}".format(round(np.std(self.getDerivedTimeSeriesValues(4, collection_idx)), 5)))

    self.derivedGrid.SetCellValue(5, 0, "% RoB Cycles stalled")
    if total_num_cycles > 0:
      value_str =str(round((float(self.current_collection_events["RESOURCE_STALLS:ROB"]) / total_num_cycles)*100, 5))
    else:
      value_str = "-"
    self.derivedGrid.SetCellValue(5, 1, value_str)
    if self.timeProfiled: self.derivedGrid.SetCellValue(5, 2,
                                  "{:,}".format(round(np.std(self.getDerivedTimeSeriesValues(5, collection_idx)), 5)))

    self.derivedGrid.SetCellValue(6, 0, "% branch misspredict")
    if self.current_collection_events["BR_INST_RETIRED:ALL_BRANCHES"] > 0:
      value_str=str(round((float(self.current_collection_events["BR_MISP_RETIRED:ALL_BRANCHES"]) /
                                            self.current_collection_events["BR_INST_RETIRED:ALL_BRANCHES"])*100, 5))
    else:
      value_str = "-"
    self.derivedGrid.SetCellValue(6, 1, value_str)
    if self.timeProfiled: self.derivedGrid.SetCellValue(6, 2,
                                  "{:,}".format(round(np.std(self.getDerivedTimeSeriesValues(6, collection_idx)), 5)))

    self.derivedGrid.SetCellValue(7, 0, "CPI")
    if self.current_collection_events["INST_RETIRED:ANY_P"] > 0:
      value_str=str(round(total_num_cycles/ float(self.current_collection_events["INST_RETIRED:ANY_P"]), 5))
    else:
      value_str = "-"
    self.derivedGrid.SetCellValue(7, 1, value_str)
    if self.timeProfiled: self.derivedGrid.SetCellValue(7, 2,
                                  "{:,}".format(round(np.std(self.getDerivedTimeSeriesValues(7, collection_idx)), 5)))

    self.derivedGrid.SetCellValue(8, 0, "% long misses")
    if self.current_collection_events["LONGEST_LAT_CACHE:REFERENCE"] > 0:
      value_str = str(round((float(self.current_collection_events["LONGEST_LAT_CACHE:MISS"]) /
                                            self.current_collection_events["LONGEST_LAT_CACHE:REFERENCE"])*100, 5))
    else:
      value_str = "-"
    self.derivedGrid.SetCellValue(8, 1, value_str)
    if self.timeProfiled: self.derivedGrid.SetCellValue(8, 2,
                                  "{:,}".format(round(np.std(self.getDerivedTimeSeriesValues(8, collection_idx)), 5)))

    self.derivedGrid.SetCellValue(9, 0, "% total execution stalls")
    if total_num_cycles > 0:
      value_str = str(round((float(self.current_collection_events["CYCLE_ACTIVITY:STALLS_TOTAL"]) / total_num_cycles)*100, 5))
    else:
      value_str = "-"
    self.derivedGrid.SetCellValue(9, 1, value_str)
    if self.timeProfiled: self.derivedGrid.SetCellValue(9, 2,
                                  "{:,}".format(round(np.std(self.getDerivedTimeSeriesValues(9, collection_idx)), 5)))

    self.derivedGrid.SetCellValue(10, 0, "% execution stalls L2")
    if total_num_cycles > 0:
      value_str = str(round((float(self.current_collection_events["CYCLE_ACTIVITY:STALLS_L2_PENDING"]) / total_num_cycles)*100, 5))
    else:
      value_str = "-"
    self.derivedGrid.SetCellValue(10, 1, value_str)
    if self.timeProfiled: self.derivedGrid.SetCellValue(10, 2,
                                  "{:,}".format(round(np.std(self.getDerivedTimeSeriesValues(10, collection_idx)), 5)))

    self.derivedGrid.SetCellValue(11, 0, "% execution stalls L1")
    if total_num_cycles > 0:
      value_str = str(round((float(self.current_collection_events["CYCLE_ACTIVITY:STALLS_L1D_PENDING"]) / total_num_cycles)*100, 5))
    else:
      value_str = "-"

    self.derivedGrid.SetCellValue(11, 1, value_str)
    if self.timeProfiled: self.derivedGrid.SetCellValue(11, 2,
                                  "{:,}".format(round(np.std(self.getDerivedTimeSeriesValues(11, collection_idx)), 5)))

    self.derivedGrid.SetCellValue(12, 0, "% execution stall on memory")
    if total_num_cycles > 0:
      value_str = str(round((float(self.current_collection_events["CYCLE_ACTIVITY:STALLS_LDM_PENDING"]) / total_num_cycles)*100, 5))
    else:
      value_str = "-"
    self.derivedGrid.SetCellValue(12, 1, value_str)
    if self.timeProfiled: self.derivedGrid.SetCellValue(12, 2,
                                  "{:,}".format(round(np.std(self.getDerivedTimeSeriesValues(12, collection_idx)), 5)))

    self.derivedGrid.SetCellValue(13, 0, "Estimated execution time (s)")
    self.derivedGrid.SetCellValue(13, 1, str(
      round(float(self.current_collection_events["CPU_CLK_THREAD_UNHALTED:REF_XCLK"]) / 100000000, 5)))
    if self.timeProfiled: self.derivedGrid.SetCellValue(13, 2,
                                  "{:,}".format(round(np.std(self.getDerivedTimeSeriesValues(13, collection_idx)), 5)))
    self.derivedGrid.AutoSize()

  def refreshProfileData(self):
    self.parseProfileReportForCollection()
    self.updateProfilingReport()
    self.updateMetrics()
    self.topLevelPanel.updateSourceCodeDisplay()

  def comboBoxChange(self, c):
    self.refreshProfileData()

class TopLevelPanel(wx.Panel):
  def __init__(self, parent, source_filecontents, event_descriptor_filename):
    wx.Panel.__init__(self, parent)
    self.parent=parent
    self.event_descriptors=self.parseEventDescriptor(event_descriptor_filename)
    self.source_filecontents=source_filecontents
    self.profile_points=self.parseProfilePoints(source_filecontents)
    self.firstLine=""
    self.my_text = html2.WebView.New()
    self.my_text.Create(self)
    self.Bind(html2.EVT_WEBVIEW_LOADED, self.pageLoaded, self.my_text)

    sizer = wx.BoxSizer(wx.HORIZONTAL)
    sizer.Add(self.my_text, 1, wx.ALL | wx.EXPAND)

    self.tabs=wx.Notebook(self)
    self.tabList=[]

    sizer.Add(self.tabs, 1, wx.EXPAND)
    self.SetSizer(sizer)

  def parseEventDescriptor(self, filename):
    json_data = open(filename).read()

    data = json.loads(json_data)
    data_dict = {}
    for item in data:
      key = item["EventName"]
      data_dict[key] = item
    return data_dict

  def loadProfileFile(self, filename):
    self.tabList.append(TabPanel(self.tabs, self, self.profile_points, filename, self.event_descriptors))
    self.tabs.AddPage(self.tabList[-1], filename.split("/")[-1].strip())
    self.tabList[-1].refreshProfileData()

  def getSelectedTab(self):
    return self.tabList[self.tabs.GetSelection()]

  def pageLoaded(self, c):
    retV = self.my_text.Find(self.firstLine, wx.html2.WEBVIEW_FIND_WRAP)
    retV = self.my_text.Find(self.firstLine, wx.html2.WEBVIEW_FIND_WRAP)

  def parseProfilePoints(self, source_contents):
    line_count = 1
    started_line = 0
    profile_points = {}
    for line in source_contents.split("\n"):
      if "startEventGathering" in line:
        started_line = line_count
      if "checkpointEventGathering" in line:
        profile_points[line_count] = started_line
      line_count += 1
    return profile_points

  def updateSourceCodeDisplay(self):
    selectedProfile=self.getSelectedTab().profile_collection_chooser.GetSelection()
    starting_linenums=list(self.profile_points.values())
    starting_linenums.sort()
    selectedLineStart=starting_linenums[selectedProfile]
    html_string=""
    line_num=1
    firstL=False
    for line in self.source_filecontents.split("\n"):
      if "startEventGathering" in line:
        if (line_num == selectedLineStart):
          firstL=True
          html_string+="<p style=\"background-color:rgba(255, 0, 0, 0.3)\">"
        else:
          html_string += "<p style=\"background-color:rgba(0, 0, 255, 0.2)\">"
      line_num_str=str(line_num)
      for i in range(len(line_num_str), 4):
        line_num_str+="&nbsp;"
      html_string+="<b>"+line_num_str+"</b>"+cgi.escape(line).replace("\t", "&nbsp;&nbsp;")+"<br>"
      if firstL:
        self.firstLine=(line_num_str+cgi.escape(line).replace("\t", "&nbsp;&nbsp;")).replace("&nbsp;", " ")
        firstL=False
      line_num+=1
      if "checkpointEventGathering" in line:
        html_string+="</p>"

    self.my_text.SetPage(html_string, "")

class MyFrame(wx.Frame):
  def __init__(self, source_filename, event_descriptor_filename):
    wx.Frame.__init__(self, None, title='Profile explorer')

    menubar = wx.MenuBar()
    fileMenu = wx.Menu()
    fileItem = fileMenu.Append(0, 'Load profile', 'Load profile')
    self.Bind(wx.EVT_MENU, self.loadProfile, fileItem)
    menubar.Append(fileMenu, '&File')
    self.SetMenuBar(menubar)
    self.panel = TopLevelPanel(self, self.getSourceContents(source_filename), event_descriptor_filename)
    self.Maximize(True)
    self.Show()

  def loadProfile(self, c):
    fileDialog=wx.FileDialog(self, "Open profile file", wildcard="Profile files (*.prof)|*.prof",
                  style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)

    if fileDialog.ShowModal() == wx.ID_CANCEL:
      return  # the user changed their mind

    # Proceed loading the file chosen by the user
    pathname = fileDialog.GetPath()
    try:
      with open(pathname, 'r') as file:
        self.panel.loadProfileFile(file.name)
    except IOError:
      wx.LogError("Cannot open file '%s'." % file)

  def getSourceContents(self, source_filename):
    contents=""
    file = open(source_filename, "r")
    for line in file:
      contents+=line
    file.close()
    return contents

class CanvasPanel(wx.Panel):
  def __init__(self, parent, data):
    wx.Panel.__init__(self, parent)
    self.figure = Figure()
    self.data=data
    self.axes = self.figure.add_subplot(111)
    self.canvas = FigureCanvas(self, -1, self.figure)
    self.sizer = wx.BoxSizer(wx.VERTICAL)
    self.sizer.Add(self.canvas, 1, wx.LEFT | wx.TOP | wx.GROW)
    self.SetSizer(self.sizer)
    self.Fit()

  def draw(self):
    str_type=str(type(self.data))
    if "numpy.ndarray" in str_type:
      self.axes.get_yaxis().get_major_formatter().set_scientific(False)
      self.axes.plot(self.data)
    elif "tuple" in str_type:
      hist=self.data[0]
      bins = self.data[1]
      width = 0.7 * (bins[1] - bins[0])
      center = (bins[:-1] + bins[1:]) / 2
      self.axes.get_xaxis().get_major_formatter().set_scientific(False)
      self.axes.bar(center, hist, align='center', width=width)

class OtherFrame(wx.Frame):
  def __init__(self, title, data, parent=None):
    wx.Frame.__init__(self, parent=parent, title=title, size=(1000,800))
    panel = CanvasPanel(self, data)
    panel.draw()
    self.Show()

if __name__ == '__main__':
  app = wx.App(False)
  frame = MyFrame(sys.argv[1], "broadwell_core_v23.json")
  app.MainLoop()


