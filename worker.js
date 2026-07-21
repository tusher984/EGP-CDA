// worker.js - Background Processing Engine

let globalData = [];
let filteredData = [];

const RULE_TITLES = {
    owner: "e-PG3 ITT 5.14 – Beneficial Ownership Disclosure",
    split: "PPA 2006 Section 17 – Artificial Contract Splitting",
    cpv: "EU CPV Regulation / e-GP Metadata Manipulation",
    tailored: "PPR 2008 Rule 98 – Restrictive Qualification Criteria",
    monopoly: "e-PG3 ITT 50.6 – Lack of Effective Competition",
    outlier: "World Bank ALB Guideline",
    meeting: "PPR Schedule 2 – Minimum Tender Preparation Time",
    rigging: "Competition Act 2012 / Bid Rigging"
};

const safeStr = (val) => (val ? String(val).toLowerCase() : "");
const safeNum = (val) => {
    if (!val) return 0;
    if (typeof val === 'number') return val;
    return parseFloat(String(val).replace(/,/g, '')) || 0;
};

function parseBDT(str) {
    if (!str) return 0;
    let s = String(str).toLowerCase().replace(/,/g, '');
    let val = parseFloat(s.match(/[\d\.]+/)?.[0]) || 0;
    if (s.includes('crore') || s.includes('core')) val *= 10000000;
    else if (s.includes('lac') || s.includes('lakh')) val *= 100000;
    return val;
}

function analyzeEligibilityAI(text, reasonsArray = []) {
    if (!text) return false;
    let score = 0, t = safeStr(text);
    if (/\d+\.[1-9]\d+\s*(crore|lac|lakh)/i.test(t)) { score += 50; reasonsArray.push("অস্বাভাবিক দশমিক সংখ্যার অভিজ্ঞতা।"); }
    if (/(office|branch office|industry)\s+(must be|should be)?\s*(situated|located)?\s*(in|within)\s+(chattogram|chittagong|dhaka|khulna|rajshahi|sylhet|barisal|rangpur)/i.test(t)) { score += 50; reasonsArray.push("ভৌগোলিক লকিং (Geofencing)।"); }
    if (/\b(rajuk|cda|kda|rda|coxda|gda|pwd|lged|city corporation|petrobangla)\b/i.test(t)) { score += 20; reasonsArray.push("নির্দিষ্ট সংস্থার (Authority Locking) নাম।"); }
    if (t.includes("single contract") || t.includes("একক চুক্তি")) { score += 20; reasonsArray.push("'Single Contract' লকিং।"); }
    if (/(last 1 year|within 12 months|১ বছরের মধ্যে|last 2 years)/i.test(t)) { score += 20; reasonsArray.push("স্বল্প সময়ের অভিজ্ঞতা।"); }
    return score >= 50; 
}

function getDynamicFindings(t) {
    let findingsList = [], ruleKeys = [];
    const fullText = Object.values(t).map(v => safeStr(v)).join(" ");
    const rReason = safeStr(t.Red_Flag_Reason), exp = safeStr(t.Eligibility_of_Tenderer || t.Extracted_Specific_Experience || t.Qualification_Criteria);
    const desc = safeStr(t.Brief_Description_of_Works || t.Brief_Description_of_Goods_and_Related_Service), pkgNo = safeStr(t.Invitation_Reference || t.Package_No);
    const sold = safeNum(t.Tenders_Sold), recv = safeNum(t.Tenders_Received), resp = safeNum(t.Responsive_Tenders), val = safeNum(t.Contract_Value_BDT), docPrice = safeNum(t.Document_Price_BDT);

    if (/beneficial owner missing/i.test(rReason) || t.Beneficial_Owner === false || t.Beneficial_Owner === "Missing") { findingsList.push({ name: "Beneficial Owner Hidden", ev: "মালিকানা গোপন।" }); ruleKeys.push('owner'); }
    if (/split|artificial/i.test(rReason) || /\(lot-[0-9a-z]+\)|part-[0-9a-z]+/i.test(desc) || /\(lot-[0-9a-z]+\)/i.test(pkgNo)) { findingsList.push({ name: "Artificial Splitting", ev: "লটে বিভাজন।" }); ruleKeys.push('split'); }
    if (/cpv manipulation/i.test(rReason) || (safeStr(t.CPV_Code).includes("000000")) || (docPrice > 0 && docPrice <= 50 && val > 1000000)) { findingsList.push({ name: "Metadata Manipulated", ev: "ভুল CPV বা অস্বাভাবিক ফি।" }); ruleKeys.push('cpv'); }
    
    let isTailored = false, tailoredEv = [];
    let reqTurnover = parseBDT(t.Extracted_Turnover), reqLiq = parseBDT(t.Extracted_Liquid_Assets);
    if (reqLiq > 0 && reqTurnover > 0 && reqLiq >= reqTurnover) { isTailored = true; tailoredEv.push(`লিকুইড মানি টার্নওভারের সমান।`); }
    if (analyzeEligibilityAI(exp, tailoredEv) || /tailored/i.test(rReason)) { isTailored = true; if(tailoredEv.length===0) tailoredEv.push("অস্বাভাবিক শর্ত।"); }
    if (isTailored) { findingsList.push({ name: "Tailored Criteria", ev: tailoredEv.join(" ") }); ruleKeys.push('tailored'); }

    if (resp === 1 && recv === 1 && sold === 1) { findingsList.push({ name: "Zero Competition", ev: "মাত্র ১ জন জমা ও কাজ পেয়েছে।" }); ruleKeys.push('monopoly'); } 
    else if (resp === 1 || /single responsive/i.test(rReason)) { findingsList.push({ name: "Monopoly", ev: "মাত্র ১ জনকে যোগ্য করা হয়েছে।" }); ruleKeys.push('monopoly'); }

    const valStr = String(t.Contract_Value_BDT || "");
    if (valStr.includes('.') && valStr.split('.')[1].length >= 3 && val > 100000) { findingsList.push({ name: "Engineered Match", ev: `৩-ডিজিটের ভগ্নাংশ।` }); ruleKeys.push('outlier'); }
    else if (/(outlier|abnormal|alb)/i.test(fullText)) { findingsList.push({ name: "Abnormal Bid", ev: "অস্বাভাবিক দর।" }); ruleKeys.push('outlier'); }

    let adDate = new Date(t.Advertised_Date), closeDate = new Date(t.Tender_Valid_Up_To), noaDate = new Date(t.Notification_of_Award_Date), signDate = new Date(t.Contract_Signing_Date);
    if (!isNaN(adDate) && !isNaN(closeDate) && Math.ceil((closeDate - adDate) / 86400000) <= 14) { findingsList.push({ name: "Rush Tender", ev: "<১৪ দিনে টেন্ডার ক্লোজ।" }); ruleKeys.push('meeting'); }
    else if (!isNaN(noaDate) && !isNaN(signDate) && Math.ceil((signDate - noaDate) / 86400000) <= 3) { findingsList.push({ name: "Lightning Execution", ev: "৩ দিনে চুক্তি স্বাক্ষর।" }); ruleKeys.push('meeting'); }

    if (sold > 0 && recv > 0 && sold >= (recv * 1.5) && sold >= 3) { findingsList.push({ name: "High Dropout (Rigging)", ev: `কিনেছে ${sold}, জমা ${recv}।` }); ruleKeys.push('rigging'); }

    if (findingsList.length === 0 && t.Red_Flag_Reason && !['no significant issue detected', 'clean', '-'].includes(rReason)) findingsList.push({ name: t.Red_Flag_Reason, ev: "সিস্টেম ফ্ল্যাগ।" });

    let html = findingsList.length > 0 ? findingsList.map(f => `<strong style="color:#fca5a5; display:block; margin-bottom:2px;">${f.name}</strong><span style="color:#94a3b8; font-size:11px; line-height:1.4; display:block;"><i>প্রমাণ: ${f.ev}</i></span>`).join("<div style='margin-bottom:8px;'></div>") : "-";
    let csv = findingsList.length > 0 ? findingsList.map(f => `${f.name} (Proof: ${f.ev})`).join(" + ") : "-";
    let uniqueRules = [...new Set(ruleKeys)];
    let rulesHtml = uniqueRules.length > 0 ? uniqueRules.map(key => `<span class="clickable-rule" onclick="showModal('${key}')">${RULE_TITLES[key].split('–')[0].trim()} ↗</span>`).join("<br><br>") : "-";
    let rulesCsv = uniqueRules.length > 0 ? uniqueRules.map(key => RULE_TITLES[key]).join(" | ") : "-";

    return { 
        html, csv, rulesHtml, rulesCsv, 
        keys: { 
            owner: uniqueRules.includes('owner'), split: uniqueRules.includes('split'), 
            cpv: uniqueRules.includes('cpv'), tailored: uniqueRules.includes('tailored'), 
            monopoly: uniqueRules.includes('monopoly'), outlier: uniqueRules.includes('outlier'), 
            meeting: uniqueRules.includes('meeting'), rigging: uniqueRules.includes('rigging') 
        } 
    };
}

// Communication Interface
self.onmessage = function(e) {
    const { action, payload } = e.data;

    if (action === 'INIT_DATA') {
        const rawData = payload;
        
        globalData = rawData.map(t => {
            t._findings = getDynamicFindings(t);
            t._searchStr = Object.values(t).map(v => safeStr(v)).join(' ');
            return t;
        });
        
        filteredData = [...globalData];
        self.postMessage({ action: 'DATA_READY', data: filteredData });
    }

    if (action === 'APPLY_FILTER') {
        const { term, risk, activeRuleKey } = payload;
        
        filteredData = globalData.filter(t => {
            if (risk !== 'ALL' && t.Risk_Level !== risk) return false;
            if (term && !t._searchStr.includes(term)) return false;
            if (activeRuleKey && t._findings.keys[activeRuleKey] !== true) return false;
            return true;
        });

        self.postMessage({ action: 'FILTER_COMPLETE', data: filteredData });
    }
};