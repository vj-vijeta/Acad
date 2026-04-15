import pandas as pd
import os

# Define file paths
data_dir = "/Users/vijeta/Documents/2025 data acad"
input_2025_path = os.path.join(data_dir, "Supporting data-13th March 2026.xlsx - 2025.csv")
input_2026_path = os.path.join(data_dir, "Supporting data-13th March 2026.xlsx - 2026.csv")
input_drops_path = "/Users/vijeta/Downloads/Supporting data-13th March 2026.xlsx - Drop schools 2026.csv"

# Output paths
output_schools_2025 = os.path.join(data_dir, "schools_by_category_2025.csv")
output_city_summary = os.path.join(data_dir, "city_wise_summary_2025.csv")
output_churn_list = os.path.join(data_dir, "churn_analysis_2026_from_list.csv")
output_churn_comparison = os.path.join(data_dir, "churn_comparison_2025_vs_2026.csv")

def get_products(row):
    prods = set()
    offering = str(row.get('Offering', '')).lower()
    
    # helper to convert to float safely
    def to_float(val):
        try:
            return float(val) if pd.notnull(val) else 0.0
        except:
            return 0.0

    # ASSET Check
    if 'asset' in offering or to_float(row.get('ASSET Revenue', 0)) > 0 or to_float(row.get('ASSETStudents', 0)) > 0:
        prods.add('ASSET')
        
    # Mindspark Check
    if 'mindspark' in offering or to_float(row.get('Mindspark Revenue', 0)) > 0 or to_float(row.get('MindsparkStudents', 0)) > 0:
        prods.add('Mindspark')
        
    # CARES Check
    if 'cares' in offering or to_float(row.get('CARES Revenue', 0)) > 0 or to_float(row.get('CARESStudents', 0)) > 0:
        prods.add('CARES')
        
    return prods

def analyze_2025():
    print("Analyzing 2025 data...")
    df = pd.read_csv(input_2025_path)
    df['City'] = df['City'].fillna('Unknown').str.strip().str.title()
    
    df['Product_Set'] = df.apply(get_products, axis=1)
    df['Product_List'] = df['Product_Set'].apply(lambda s: sorted(list(s)))
    df['Prod_Count'] = df['Product_List'].apply(len)
    
    def categorize(row):
        count = row['Prod_Count']
        prods = row['Product_List']
        if count == 1:
            return f"Only {prods[0]}"
        elif count == 2:
            return "2 Products"
        elif count == 3:
            return "All Products"
        else:
            return "No specified products"

    df['Category'] = df.apply(categorize, axis=1)
    
    df_list = df[['School No', 'School Name', 'City', 'Category', 'Offering']].sort_values(['Category', 'School Name'])
    df_list.to_csv(output_schools_2025, index=False)
    
    summary = df.groupby(['City', 'Category']).size().unstack(fill_value=0)
    req_cols = ["Only ASSET", "Only Mindspark", "Only CARES", "2 Products", "All Products"]
    for c in req_cols:
        if c not in summary.columns:
            summary[c] = 0
    summary['Total Schools'] = summary.sum(axis=1)
    summary = summary[['Total Schools'] + req_cols]
    summary.to_csv(output_city_summary)

def analyze_2026_drops_from_list():
    print("Analyzing 2026 drops from provided list...")
    if not os.path.exists(input_drops_path):
        return

    df_drops = pd.read_csv(input_drops_path)
    def classify_drop(row):
        reason = str(row.get('Reasons', '')).lower()
        if 'partial' in reason:
            return 'Partially Dropped'
        return 'Dropped'

    df_drops['Drop Category'] = df_drops.apply(classify_drop, axis=1)
    df_result = df_drops[['School No.', 'School Name', 'Products', 'Drop Category', 'Reasons']]
    df_result.to_csv(output_churn_list, index=False)

def analyze_comparison():
    print("Comparing 2025 vs 2026 data...")
    df25 = pd.read_csv(input_2025_path)
    df26 = pd.read_csv(input_2026_path)

    # Use School No as key
    df25['School No'] = df25['School No'].astype(str).str.strip()
    df26['School No'] = df26['School No'].astype(str).str.strip()

    # Get products for each school
    df25['P25'] = df25.apply(get_products, axis=1)
    df26['P26'] = df26.apply(get_products, axis=1)

    # Dictionary for 2026 lookups
    dict26 = df26.set_index('School No')['P26'].to_dict()

    results = []
    for _, row in df25.iterrows():
        s_no = row['School No']
        s_name = row['School Name']
        p25 = row['P25']
        
        if not p25: # Skip if no products in 2025
            continue
            
        if s_no not in dict26:
            # Dropped entirely
            results.append({
                'School No': s_no,
                'School Name': s_name,
                'Status': 'Dropped',
                'Products 2025': ", ".join(sorted(list(p25))),
                'Products 2026': "None",
                'Dropped Products': ", ".join(sorted(list(p25)))
            })
        else:
            p26 = dict26[s_no]
            dropped_from_p25 = p25 - p26
            if dropped_from_p25:
                results.append({
                    'School No': s_no,
                    'School Name': s_name,
                    'Status': 'Partially Dropped',
                    'Products 2025': ", ".join(sorted(list(p25))),
                    'Products 2026': ", ".join(sorted(list(p26))) if p26 else "None",
                    'Dropped Products': ", ".join(sorted(list(dropped_from_p25)))
                })

    df_churn = pd.DataFrame(results)
    df_churn.to_csv(output_churn_comparison, index=False)
    print(f"Generated {output_churn_comparison}")

def analyze_full_report():
    print("Generating full school status report...")
    df25 = pd.read_csv(input_2025_path)
    df26 = pd.read_csv(input_2026_path)

    df25['School No'] = df25['School No'].astype(str).str.strip()
    df26['School No'] = df26['School No'].astype(str).str.strip()

    df25['P25'] = df25.apply(get_products, axis=1)
    df26['P26'] = df26.apply(get_products, axis=1)
    dict26 = df26.set_index('School No')['P26'].to_dict()

    def get_status(row):
        s_no = row['School No']
        p25 = row['P25']
        if not p25: return "N/A"
        if s_no not in dict26: return "Dropped"
        p26 = dict26[s_no]
        if p25 - p26: return "Partially Dropped"
        return "Retained"

    df25['Dropped/Retained'] = df25.apply(get_status, axis=1)

    # Filter for only dropped/partially dropped
    df_dropped_only = df25[df25['Dropped/Retained'].isin(['Dropped', 'Partially Dropped'])]

    # Requested Columns
    requested_cols = [
        "School Type", "School No", "School Name", "Dropped/Retained", "Academic Year", "SSF Date", "Offering", 
        "School Revenue Type", "SSF Number", "Status", "Total Order Value (Exclusive GST)", 
        "Total Order Value (Inclusive GST)", "ASSET Revenue", "ASSETStudents", "ASSET rate", 
        "CARES Revenue", "CARESStudents", "CARES rate", "Mindspark Revenue", "MindsparkStudents", 
        "Mindspark rate", "Teacher Training Revenue", "Payment Mode", "No Of Installments", 
        "Full Payment Date", "First Installment Date", "First Installment Amount", "Second Installment Date", 
        "Second Installment Amount", "Third Installment Date", "Third Installment Amount", 
        "Fourth Installment Date", "Fourth Installment Amount", "TDS Amount", "First payment Date", 
        "Latest payment Date", "To be invoiced till date", "Amount Received", "Due till date as per payment schedule", 
        "Total Discount %", "Standard Discount %", "Pre Payment Discount %", "Volume Discount %", 
        "Bundle Discount %", "Loyalty Discount %", "ASSETRound", "Ei ASSET Mode", "CAREStestpack", 
        "Ei CARES Version", "Ei CARES Mode Of Printing", "Ei CARES Mode", "Ei Mindspark Mode", 
        "Board", "City", "State", "Division", "Zone", "Vertical", "Program Start Date", 
        "Program End Date", "Order Type", "ID", "Zoho CRM Account ID", "Deal ID", "Created Date", 
        "Added User", "Modified User", "SSF Creator Email", "SSF Creator", "CRM Account Owner", 
        "CRM Acad Consultant", "Logistic Approved Date", "SSF Signing Perosn Name", 
        "SSF Signing Perosn Designation", "SSF Signing Perosn Mail ID", "SSF Signing Perosn Phone No", 
        "School CRM Email", "Principal Name", "Principal Email", "Principal Phone No", "Coordinator Name", 
        "Coordinator Email", "Coordinator Phone No", "School Fees", "Billing Address Line 1", 
        "Billing Address Line 2", "Billing Postal Code", "Shipping Address Line 1", "Shipping City", 
        "Shipping State", "Shipping Postal Code", "TAN NO", "CRM Billing Street", "CRM Shipping Street"
    ]

    # Ensure all columns exist, if not fill with #N/A or empty
    for col in requested_cols:
        if col not in df_dropped_only.columns:
            df_dropped_only[col] = "#N/A"

    df_final = df_dropped_only[requested_cols]
    output_full_report = os.path.join(data_dir, "dropped_schools_full_data.csv")
    df_final.to_csv(output_full_report, index=False)
    print(f"Generated {output_full_report}")

if __name__ == "__main__":
    analyze_2025()
    analyze_2026_drops_from_list()
    analyze_comparison()
    analyze_full_report()
    print("Done.")
