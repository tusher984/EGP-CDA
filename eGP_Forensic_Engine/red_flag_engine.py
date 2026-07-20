import pandas as pd
import numpy as np
import logging
import json
import re
import os
import difflib
from collections import defaultdict

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# =========================================================
# 1. ENTITY RESOLUTION & CLEANING MODULE
# =========================================================
class DataNormalizer:
    @staticmethod
    def normalize_corporate_name(name):
        """Standardizes contractor names to eliminate fuzzy naming variations."""
        if not name or pd.isna(name): 
            return ""
        name = str(name).lower().strip()
        # Remove common corporate suffixes to extract the core brand entity
        name = re.sub(r'\b(ltd|limited|inc|corp|co|enterprise|enterprises|bd|construction|engr|engineering)\b', '', name)
        name = re.sub(r'[^\w\s]', '', name)
        return re.sub(r'\s+', ' ', name).strip()

    @staticmethod
    def calculate_fuzzy_match(name1, name2):
        """Native fallback for Levenshtein ratio using difflib SequenceMatcher."""
        if not name1 or not name2: 
            return 0.0
        return difflib.SequenceMatcher(None, name1, name2).ratio()

    @staticmethod
    def safe_float(val):
        if pd.isna(val) or val == '' or val is None or str(val).lower() == 'nan':
            return 0.0
        try:
            return float(str(val).replace(',', '').strip())
        except ValueError:
            return 0.0

# =========================================================
# 2. CROSS-TENDER AND CARTEL ANALYZER
# =========================================================
class CrossTenderAnalyzer:
    def __init__(self, df):
        self.df = df.copy()
        self.df['Normalized_Supplier'] = self.df['Supplier_Name'].apply(DataNormalizer.normalize_corporate_name)
        self.df['Clean_Award_Value'] = self.df['Contract_Value_BDT'].apply(DataNormalizer.safe_float)
        
    def analyze_repeat_winners(self):
        """Identifies contractors holding disproportionate contract counts or monopoly power."""
        counts = self.df[self.df['Normalized_Supplier'] != '']['Normalized_Supplier'].value_counts().to_dict()
        return counts

    def detect_split_procurement(self):
        """Spots potential contract splitting designed to artificially bypass open tender ceilings."""
        split_triggers = defaultdict(list)
        
        # Group by identical PE, Category, and Date vectors
        for idx, row in self.df.iterrows():
            pe = str(row.get('Procuring_Entity_Name', ''))
            cat = str(row.get('Category', ''))
            date = str(row.get('Advertised_Date', ''))
            tid = str(row.get('Tender_Proposal_ID', ''))
            
            if pe and cat and date and tid:
                key = f"{pe}||{cat}||{date}"
                split_triggers[key].append(idx)
                
        return {k: v for k, v in split_triggers.items() if len(v) > 1}

    def compute_market_concentration(self):
        """Calculates market share and Herfindahl-Hirschman Index (HHI) for market capture."""
        total_market_value = self.df['Clean_Award_Value'].sum()
        if total_market_value == 0:
            return {}, 0
            
        supplier_shares = self.df.groupby('Normalized_Supplier')['Clean_Award_Value'].sum()
        supplier_share_pct = (supplier_shares / total_market_value) * 100
        
        # Compute HHI Formula
        hhi = np.sum(supplier_share_pct ** 2)
        return supplier_share_pct.to_dict(), hhi

# =========================================================
# 3. STATISTICAL OUTLIER ANALYZER (IQR & Modified Z-Score)
# =========================================================
class StatisticalOutlierAnalyzer:
    def __init__(self, df):
        self.values = df['Contract_Value_BDT'].apply(DataNormalizer.safe_float).replace(0, np.nan).dropna()
        if len(self.values) > 0:
            self.median = self.values.median()
            self.q1 = self.values.quantile(0.25)
            self.q3 = self.values.quantile(0.75)
            self.iqr = self.q3 - self.q1
            # Robust Median Absolute Deviation (MAD) implementation
            self.mad = np.median(np.abs(self.values - self.median))
            if self.mad == 0: 
                self.mad = 1.0  # Avoid zero-division error in uniform sets
        else:
            self.median, self.iqr, self.mad = 0, 0, 1.0

    def compute_modified_z_score(self, val):
        """Calculates Modified Z-Score using MAD framework for robust anomaly detection."""
        if len(self.values) == 0 or self.mad == 0: 
            return 0.0
        return 0.6745 * (val - self.median) / self.mad

# =========================================================
# 4. TIMELINE AND COMPLIANCE GAP MODULE
# =========================================================
class TimelineForensicAnalyzer:
    @staticmethod
    def calculate_gap_days(date_start, date_end):
        try:
            if pd.isna(date_start) or pd.isna(date_end): 
                return np.nan
            return (pd.to_datetime(date_end) - pd.to_datetime(date_start)).days
        except Exception:
            return np.nan

# =========================================================
# 5. CORE DYNAMIC FORENSIC ARCHITECTURE
# =========================================================
class ForensicIntelligencePlatform:
    def __init__(self, input_csv="Omnibus_Procurement_Database.csv"):
        self.input_csv = input_csv
        self.df = pd.read_csv(input_csv)
        self.cross_analyzer = CrossTenderAnalyzer(self.df)
        self.stat_analyzer = StatisticalOutlierAnalyzer(self.df)

    def process_pipeline(self, output_csv="Detailed_Compliance_Triggers.csv"):
        logging.info("Initializing multi-layer cross-tender calculations...")
        winner_counts = self.cross_analyzer.analyze_repeat_winners()
        split_groups = self.cross_analyzer.detect_split_procurement()
        market_shares, hhi_index = self.cross_analyzer.compute_market_concentration()
        
        logging.info(f"Global Market Concentration Index (HHI calculated): {hhi_index:.2f}")
        
        compiled_forensic_leads = []

        for idx, row in self.df.iterrows():
            tender_id = str(row.get('Tender_Proposal_ID', 'Unknown'))
            pe_name = str(row.get('Procuring_Entity_Name', 'Unknown'))
            supplier = str(row.get('Supplier_Name', 'None'))
            norm_supplier = DataNormalizer.normalize_corporate_name(supplier)
            award_val = DataNormalizer.safe_float(row.get('Contract_Value_BDT', 0))
            
            # --- CROSS TENDER LOGIC ---
            # 1. Repeat Winner Checks
            if norm_supplier and winner_counts.get(norm_supplier, 0) > 15:
                compiled_forensic_leads.append(self.create_lead(
                    tender_id, pe_name, "COMP_001", "e-PG3A / PPR 149", "Competition",
                    "Dominant Repeat Winner Pattern",
                    f"Contractor won {winner_counts[norm_supplier]} total contracts across database.",
                    "High", 30, "Needs Manual Review", "Cross-compare bid securities to rule out proxy bidding rings."
                ))
            
            # 2. Market Share Monopolization
            if norm_supplier and market_shares.get(norm_supplier, 0) > 10.0:
                compiled_forensic_leads.append(self.create_lead(
                    tender_id, pe_name, "COMP_002", "PPR Market Concentration Framework", "Competition",
                    "High Market Share Capture",
                    f"Contractor controls {market_shares[norm_supplier]:.2f}% of total processed procurement volume BDT.",
                    "Critical", 45, "Needs Manual Review", "Analyze framework criteria for hidden barriers restricting open entry."
                ))

            # 3. Contract Splitting Triggers
            for split_key, indices in split_groups.items():
                if idx in indices:
                    compiled_forensic_leads.append(self.create_lead(
                        tender_id, pe_name, "ELG_005", "PPA 2006 Split Prohibition", "Eligibility",
                        "Potential Artificial Contract Splitting",
                        f"Tender matched multi-contract cluster on key vector: {split_key}.",
                        "High", 25, "Possible Non-Compliance", "Audit package definitions to see if scope was sliced to evade high approval levels."
                    ))

            # --- STATISTICAL LOGIC ---
            if award_val > 0:
                mod_z = self.stat_analyzer.compute_modified_z_score(award_val)
                if abs(mod_z) > 3.5:
                    compiled_forensic_leads.append(self.create_lead(
                        tender_id, pe_name, "STAT_001", "Statistical Outlier Model via MAD", "Financial",
                        "Extreme Contract Price Outlier",
                        f"Contract value BDT {award_val:,.2f} registered a Modified Z-Score of {mod_z:.2f}.",
                        "High", 25, "Needs Manual Review", "Evaluate line-item pricing maps against historical reference curves."
                    ))

            # --- TIMELINE GAP LOGIC ---
            pub_date = row.get('Advertised_Date')
            close_date = row.get('Closing_Date')
            gap = TimelineForensicAnalyzer.calculate_gap_days(pub_date, close_date)
            if pd.notna(gap) and gap < 14:
                compiled_forensic_leads.append(self.create_lead(
                    tender_id, pe_name, "TIM_001", "PPR Timeline Framework", "Timeline",
                    "Compressed Bidding Window",
                    f"Bidding configuration open window allowed only {int(gap)} days from Notice to Closing.",
                    "Medium", 20, "Possible Non-Compliance", "Investigate if targeted competitors were pre-notified before official release."
                ))

        # Output generation
        if compiled_forensic_leads:
            df_out = pd.DataFrame(compiled_forensic_leads)
            df_out.to_csv(output_csv, index=False)
            logging.info(f"SUCCESS: Platform processed and saved {len(df_out)} deep forensic leads to '{output_csv}'.")
        else:
            logging.info("Forensic analysis sequence completed: Zero outlier thresholds triggered.")

    def create_lead(self, tid, pe, rule_id, source, cat, name, evidence, severity, base_score, status, rec):
        """Generates dynamic, fully populated compliance records for investigative workflows."""
        return {
            'Tender_Proposal_ID': tid,
            'Procuring_Entity_Name': pe,
            'Rule_ID': rule_id,
            'Rule_Reference': source,
            'Category': cat,
            'Finding': name,
            'Evidence': evidence,
            'Severity': severity,
            'Risk_Score': base_score,
            'Review_Status': status,
            'Investigative_Recommendation': rec
        }

if __name__ == "__main__":
    platform = ForensicIntelligencePlatform()
    platform.process_pipeline()