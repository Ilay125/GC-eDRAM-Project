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
                if "l1dcache.demandMisses::total" in line:
                    miss = line[line.find(" ") : line.find("#")].strip()
                    tot_stats[way_type][test_id]["miss"] = float(miss)
                if "l1dcache.conflictMisses" in line:
                    conflicts = line[line.find(" ") : line.find("#")].strip()
                    tot_stats[way_type][test_id]["conflicts"] = float(conflicts)

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

# 1. LLCbench Miss Rate
llc_df = df[df["Base"].isin(llc_ops)]

plt.figure(figsize=(14, 7))
llc_df["Test Name"] = llc_df["Test Name"] + " (" + llc_df["Size"] + "KB)"

plt.yscale('log')
plt.ylabel("Miss Rate (log-scale)")

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

llc_clean = df[df["Base"].isin(llc_ops) & (df["Size"] != "N/A")]

for op in llc_ops:
    for sz in ["8", "16", "32"]:
        row_4 = llc_clean[(llc_clean["Base"] == op) & (llc_clean["Size"] == sz) & (llc_clean["Ways"] == "4way")]
        row_6 = llc_clean[(llc_clean["Base"] == op) & (llc_clean["Size"] == sz) & (llc_clean["Ways"] == "6way")]
        
        if not row_4.empty and not row_6.empty:
            mr_4 = row_4["Miss Rate"].values[0]
            mr_6 = row_6["Miss Rate"].values[0]
            
            reduction = ((mr_4 - mr_6) / mr_4 * 100) if mr_4 > 0 else 0
            
            llc_rel_data.append({
                "Test Name": f"{name_map[op]} ({sz}KB)",
                "Reduction (%)": reduction,
                "Size_Int": int(sz)
            })

# Create DataFrame
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
plt.yscale('log')
plt.ylabel("Miss Rate (log-scale)")

plt.title("MiBench - Real-World Workload Miss Rate", fontsize=15)
plt.tight_layout()
plt.show()


# 4. MiBench CPI
plt.figure(figsize=(10, 6))
sns.barplot(data=mibench_df, x="Test Name", y="CPI", hue="Ways", palette="muted")
plt.title("MiBench - Real-World Workload CPI", fontsize=15)
plt.ylabel("CPI")
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

# --- Miss Breakdown Visualization (100% Stacked Percentage Chart) ---
mibench_tests = ["qsort", "dijkstra", "patricia", "sha", "rijndael", "fft"]
miss_percentage_data = []

for test in mibench_tests:
    for way in ["4way", "6way"]:
        if test in tot_stats[way] and "miss" in tot_stats[way][test]:
            total = tot_stats[way][test]["miss"]
            conflicts = tot_stats[way][test].get("conflicts", 0)
            
            if total > 0:
                conflict_pct = (conflicts / total) * 100
                capacity_pct = 100 - conflict_pct
            else:
                conflict_pct = 0
                capacity_pct = 0
            
            miss_percentage_data.append({
                "Test": name_map.get(test, test),
                "Ways": way,
                "Conflict Misses (%)": conflict_pct,
                "Capacity Misses (%)": capacity_pct
            })

df_pct = pd.DataFrame(miss_percentage_data)

# Separate into 4-way and 6-way DataFrames for side-by-side plotting
df_4way_pct = df_pct[df_pct["Ways"] == "4way"].set_index("Test")[["Conflict Misses (%)", "Capacity Misses (%)"]]
df_6way_pct = df_pct[df_pct["Ways"] == "6way"].set_index("Test")[["Conflict Misses (%)", "Capacity Misses (%)"]]

fig, axes = plt.subplots(1, 2, figsize=(15, 6), sharey=True)

colors = ["#e63946", "#457b9d"]

# Plot 4-Way
df_4way_pct.plot(kind="bar", stacked=True, ax=axes[0], color=colors, edgecolor="black")
axes[0].set_title("4-Way Cache: Relative Miss Breakdown", fontsize=14, weight='bold')
axes[0].set_ylabel("Percentage of Total Misses (%)", fontsize=12)
axes[0].set_xlabel("")
axes[0].tick_params(axis='x', rotation=45)
axes[0].set_ylim(0, 105) 
axes[0].grid(axis='y', linestyle='--', alpha=0.7)

# Plot 6-Way
df_6way_pct.plot(kind="bar", stacked=True, ax=axes[1], color=colors, edgecolor="black")
axes[1].set_title("6-Way Cache: Relative Miss Breakdown", fontsize=14, weight='bold')
axes[1].set_xlabel("")
axes[1].tick_params(axis='x', rotation=45)
axes[1].grid(axis='y', linestyle='--', alpha=0.7)

# Add text labels inside the bars for extra clarity
for ax in axes:
    for container in ax.containers:
        # Only show the label if the chunk is > 5% to avoid cramped text on tiny bars
        labels = [f'{v.get_height():.1f}%' if v.get_height() > 5 else '' for v in container]
        ax.bar_label(container, labels=labels, label_type='center', color='white', weight='bold', fontsize=10)

plt.suptitle("MiBench Workloads: Conflict vs. Capacity Ratio", fontsize=16, weight='bold')
plt.tight_layout()
plt.show()