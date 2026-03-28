import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import os
import re

stats_root_dir = r"stats"

llc_ops = ["b", "r", "w", "s", "p"]
sizes = ["8", "16", "32"]
mibench = ["qsort", "dijkstra", "patricia", "sha", "rijndael", "fft"]

name_map = {
    "b": "Read-Modify-Write",
    "r": "Read",
    "w": "Write",
    "s": "Memset",
    "p": "Memcpy",
    "qsort": "QuickSort",
    "dijkstra": "Dijkstra",
    "patricia": "Patricia",
    "sha": "SHA-256",
    "rijndael": "Rijndael",
    "fft": "FFT"
}

# Initialize data structure
tot_stats = {"4way": {}, "6way": {}}

# Walk through the stats directory
for root, dirs, files in os.walk(stats_root_dir):
    if "stats.txt" in files:
        file_path = os.path.join(root, "stats.txt")
        path_parts = file_path.split(os.sep)
        
        # Expecting path like: stats/4way/b16/stats.txt
        way_type = path_parts[1]
        test_id = path_parts[2]

        if test_id not in tot_stats[way_type]:
            tot_stats[way_type][test_id] = {}

        print(f"Processing {way_type} test={test_id}")
        
        with open(file_path) as file:
            for line in file:
                if "l1dcache.demandMissRate::total" in line:
                    mr = line[line.find(" ") : line.find("#")].strip()
                    tot_stats[way_type][test_id]["mr"] = float(mr)
                if "commitStats0.cpi" in line:
                    cpi = line[line.find(" ") : line.find("#")].strip()
                    tot_stats[way_type][test_id]["cpi"] = float(cpi)
                if "simInsts" in line:
                    insts = line[line.find(" ") : line.find("#")].strip()
                    # print(f"{way_type} {test_id} done {insts} inst.")

# Build DataFrame
data_list = []
for way, tests in tot_stats.items():
    for test_id, metrics in tests.items():
        if metrics: # Ensure we have data
            # Extract Size and Base Name
            # If it's something like 'b16', base='b', size='16'
            # If it's 'qsort', base='qsort', size='N/A'
            match = re.match(r"([a-z]+)([0-9]*)", test_id)
            base_code = match.group(1)
            size = match.group(2) if match.group(2) else "N/A"
            
            data_list.append({
                "Ways": way,
                "TestID": test_id,
                "Base": base_code,
                "Size": size,
                "Test Name": name_map.get(base_code, base_code),
                "Miss Rate": metrics.get("mr", 0),
                "CPI": metrics.get("cpi", 0)
            })

df = pd.DataFrame(data_list)
print(df)

# --- PLOTTING ---
sns.set_style("whitegrid")

# 1. LLCbench Miss Rate - Grouped by Size
# We show the "Read" tests (r8, r16, r32) together
llc_df = df[df["Base"].isin(llc_ops)]

plt.figure(figsize=(14, 7))
# Create a combined Label like "Read (16KB)"
llc_df["Test Name"] = llc_df["Test Name"] + " (" + llc_df["Size"] + "KB)"
sns.barplot(data=llc_df, x="Test Name", y="Miss Rate", hue="Ways", palette="muted")
plt.xticks(rotation=45)
plt.title("LLCbench - Impact of Array Size on Miss Rate", fontsize=15)
plt.tight_layout()
plt.show()

# 2. LLCbench CPI
plt.figure(figsize=(14, 7))
sns.barplot(data=llc_df, x="Test Name", y="CPI", hue="Ways", palette="muted")
plt.xticks(rotation=45)
plt.title("LLCbench - Impact of Array Size on CPI", fontsize=15)
plt.tight_layout()
plt.show()


llc_rel_data = []

# Filter for LLCbench ops and exclude 'N/A' noise
llc_clean = df[df["Base"].isin(llc_ops) & (df["Size"] != "N/A")]

# Group by the specific test (e.g., 'r8', 'w16') to compare 4way vs 6way
for op in llc_ops:
    for sz in ["8", "16", "32"]:
        row_4 = llc_clean[(llc_clean["Base"] == op) & (llc_clean["Size"] == sz) & (llc_clean["Ways"] == "4way")]
        row_6 = llc_clean[(llc_clean["Base"] == op) & (llc_clean["Size"] == sz) & (llc_clean["Ways"] == "6way")]
        
        if not row_4.empty and not row_6.empty:
            mr_4 = row_4["Miss Rate"].values[0]
            mr_6 = row_6["Miss Rate"].values[0]
            
            # Catch division by zero just in case
            reduction = ((mr_4 - mr_6) / mr_4 * 100) if mr_4 > 0 else 0
            
            llc_rel_data.append({
                "Test Name": f"{name_map[op]} ({sz}KB)",
                "Reduction (%)": reduction,
                "Size_Int": int(sz) # Used for logical sorting
            })

# Create DataFrame and sort by size then test name
llc_rel_df = pd.DataFrame(llc_rel_data)

plt.figure(figsize=(14, 7))
sns.set_style("whitegrid")

# Create the plot
llc_plot = sns.barplot(data=llc_rel_df, x="Test Name", y="Reduction (%)", palette="magma")

# Annotate bars with the percentage value
for p in llc_plot.patches:
    llc_plot.annotate(format(p.get_height(), '.2f') + '%', 
                   (p.get_x() + p.get_width() / 2., p.get_height()), 
                   ha = 'center', va = 'center', 
                   xytext = (0, 9), 
                   textcoords = 'offset points', 
                   weight='bold',
                   fontsize=9)

plt.title("LLCbench - Miss Rate Improvement", fontsize=15)
plt.ylabel("Reduction in Miss Rate (%)")
plt.xticks(rotation=45, ha='right')
plt.ylim(0, 0.1) # Scale Y to see small changes
plt.tight_layout()
plt.show()

# 3. MiBench Miss Rate
mibench_df = df[df["Base"].isin(mibench)]
plt.figure(figsize=(10, 6))
sns.barplot(data=mibench_df, x="Test Name", y="Miss Rate", hue="Ways", palette="muted")
plt.title("MiBench - Real-World Workload Miss Rate", fontsize=15)
plt.tight_layout()
plt.show()


# 4. MiBench CPI
plt.figure(figsize=(10, 6))
sns.barplot(data=mibench_df, x="Test Name", y="CPI", hue="Ways", palette="muted")
plt.title("MiBench - Real-World Workload CPI", fontsize=15)
plt.tight_layout()
plt.show()

# 5. Relative Difference (MiBench Only)
rel_diff_data = []
for t in mibench:
    row_4 = mibench_df[(mibench_df["Base"] == t) & (mibench_df["Ways"] == "4way")]
    row_6 = mibench_df[(mibench_df["Base"] == t) & (mibench_df["Ways"] == "6way")]
    
    if not row_4.empty and not row_6.empty:
        mr_4 = row_4["Miss Rate"].values[0]
        mr_6 = row_6["Miss Rate"].values[0]
        reduction = ((mr_4 - mr_6) / mr_4) * 100
        rel_diff_data.append({"Test Name": name_map[t], "Reduction (%)": reduction})

rel_df = pd.DataFrame(rel_diff_data)

plt.figure(figsize=(10, 6))
reduction_plot = sns.barplot(data=rel_df, x="Test Name", y="Reduction (%)", palette="viridis")
for p in reduction_plot.patches:
    reduction_plot.annotate(format(p.get_height(), '.1f') + '%', 
                   (p.get_x() + p.get_width() / 2., p.get_height()), 
                   ha = 'center', va = 'center', xytext = (0, 9), 
                   textcoords = 'offset points', weight='bold')

plt.title("MiBench - Miss Rate Improvement", fontsize=14)
plt.ylabel("Reduction in Miss Rate (%)")
plt.ylim(0, 100)
plt.tight_layout()
plt.show()