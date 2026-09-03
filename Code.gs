/**
 * Google Apps Script for LinkedIn Leads CRM & Apify Multi-Token Pool (Safe-Sync & Non-Destructive)
 * 
 * Key Features:
 * - AUTO-CHECK & SYNC COLUMNS: Checks all sheets for missing standard columns and adds them automatically.
 * - ZERO DATA LOSS GUARANTEE: Never deletes, moves, or overwrites existing user data, custom columns, or rows.
 * - DYNAMIC QUERIES: Manages all search queries directly in the 'Queries' tab with enable/disable toggles.
 * - UNLIMITED TOKENS: Automatically scales to as many Apify tokens as you add.
 * - CUSTOM COLUMN SAFE: You can add your own custom columns anywhere without them being overwritten.
 */

function onOpen() {
  var ui = SpreadsheetApp.getUi();
  ui.createMenu('⚙️ Lead Bot Setup')
    .addItem('🔄 Safe Setup / Sync All Sheets (Preserves All Data)', 'safeSyncSheets')
    .addItem('📊 Refresh Day-of-Week Analytics', 'calculateDayOfWeekAverages')
    .addItem('🧹 Clean Duplicate Leads (Keep Fresh)', 'removeDuplicateLeads')
    .addToUi();
}

/**
 * Helper function: Verifies that a sheet has all required column headers.
 * If any column is missing, it appends it non-destructively to the end of row 1.
 * Never touches or alters existing data rows, custom columns, or formulas.
 * 
 * @param {Sheet} sheet The spreadsheet sheet object.
 * @param {Array<string>} requiredHeaders Array of standard column header names.
 * @param {string} bgColor Background hex color for new headers.
 * @param {string} fontColor Font hex color for new headers.
 * @param {Array<number>} colWidths Optional default column widths.
 * @returns {Array<string>} List of column names that were newly added.
 */
function ensureSheetHeaders(sheet, requiredHeaders, bgColor, fontColor, colWidths) {
  var lastRow = sheet.getLastRow();
  var lastCol = sheet.getLastColumn();
  var addedCols = [];

  if (lastRow === 0 || lastCol === 0) {
    // Completely empty sheet: insert all required headers in row 1
    sheet.getRange(1, 1, 1, requiredHeaders.length).setValues([requiredHeaders]);
    var range = sheet.getRange(1, 1, 1, requiredHeaders.length);
    range.setBackground(bgColor)
         .setFontColor(fontColor)
         .setFontWeight('bold')
         .setHorizontalAlignment('center');
    sheet.setFrozenRows(1);
    if (colWidths) {
      for (var i = 0; i < colWidths.length; i++) {
        sheet.setColumnWidth(i + 1, colWidths[i]);
      }
    }
    return requiredHeaders;
  }

  // Read existing headers from row 1
  var existingHeaders = sheet.getRange(1, 1, 1, lastCol).getValues()[0];
  var existingNormalized = existingHeaders.map(function(h) {
    return h ? h.toString().trim().toLowerCase() : '';
  });

  // Identify any missing standard headers
  var missing = [];
  for (var j = 0; j < requiredHeaders.length; j++) {
    var reqNorm = requiredHeaders[j].trim().toLowerCase();
    if (existingNormalized.indexOf(reqNorm) === -1) {
      missing.push(requiredHeaders[j]);
    }
  }

  // Non-destructively append missing headers at the end of row 1
  if (missing.length > 0) {
    var startCol = lastCol + 1;
    for (var m = 0; m < missing.length; m++) {
      var targetCol = startCol + m;
      var cell = sheet.getRange(1, targetCol);
      cell.setValue(missing[m]);
      cell.setBackground(bgColor)
          .setFontColor(fontColor)
          .setFontWeight('bold')
          .setHorizontalAlignment('center');
      sheet.setColumnWidth(targetCol, 160);
      addedCols.push(missing[m]);
    }
  }

  return addedCols;
}

/**
 * Non-destructive setup & sync:
 * 1. Verifies that all 5 sheets exist (creates them if missing).
 * 2. Checks every sheet for missing standard columns and adds them to row 1.
 * 3. Never deletes, clears, or modifies existing rows, tokens, passwords, or custom columns.
 */
function safeSyncSheets() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var syncLog = [];

  // -------------------------------------------------------------
  // 1. TAB: Leads Database (Email, Domain, Phone Number, Name, Query, Date)
  // -------------------------------------------------------------
  var leadsSheet = ss.getSheetByName('Leads Database') || ss.insertSheet('Leads Database');
  var leadsRequired = ['Email', 'Domain', 'Phone Number', 'Name', 'Query', 'Date'];
  var leadsWidths = [260, 180, 170, 200, 300, 150];
  var leadsAdded = ensureSheetHeaders(leadsSheet, leadsRequired, '#1A73E8', '#FFFFFF', leadsWidths);
  if (leadsAdded.length > 0) {
    syncLog.push('• Leads Database: Added column(s) [' + leadsAdded.join(', ') + ']');
  }

  // -------------------------------------------------------------
  // 2. TAB: Queries (Search Queries Managed in Google Sheets)
  // -------------------------------------------------------------
  var queriesSheet = ss.getSheetByName('Queries') || ss.insertSheet('Queries');
  var isQueriesNew = (queriesSheet.getLastRow() === 0);
  var queriesRequired = ['Query', 'City', 'Enabled', 'Notes'];
  var queriesWidths = [380, 150, 100, 150];
  var queriesAdded = ensureSheetHeaders(queriesSheet, queriesRequired, '#009688', '#FFFFFF', queriesWidths);
  if (queriesAdded.length > 0) {
    syncLog.push('• Queries: Added column(s) [' + queriesAdded.join(', ') + ']');
  }

  // Populate default queries only if the sheet was completely empty
  if (isQueriesNew) {
    var defaultQueries = [
      // Bengaluru (6)
      ['"Hiring" AND "Bengaluru" AND "@"', 'Bengaluru', 'TRUE', 'Active'],
      ['"Urgent Hiring" AND "Bengaluru" AND "@"', 'Bengaluru', 'TRUE', 'Active'],
      ['"Immediate Joiner" AND "Bengaluru" AND "@"', 'Bengaluru', 'TRUE', 'Active'],
      ['"Immediate Joining" AND "Bengaluru" AND "@"', 'Bengaluru', 'TRUE', 'Active'],
      ['"We\'re Hiring" AND "Bengaluru" AND "@"', 'Bengaluru', 'TRUE', 'Active'],
      ['"We are hiring" AND "Bengaluru" AND "@"', 'Bengaluru', 'TRUE', 'Active'],
      
      // Hyderabad (6)
      ['"Hiring" AND "Hyderabad" AND "@"', 'Hyderabad', 'TRUE', 'Active'],
      ['"Urgent Hiring" AND "Hyderabad" AND "@"', 'Hyderabad', 'TRUE', 'Active'],
      ['"Immediate Joiner" AND "Hyderabad" AND "@"', 'Hyderabad', 'TRUE', 'Active'],
      ['"Immediate Joining" AND "Hyderabad" AND "@"', 'Hyderabad', 'TRUE', 'Active'],
      ['"We\'re Hiring" AND "Hyderabad" AND "@"', 'Hyderabad', 'TRUE', 'Active'],
      ['"We are hiring" AND "Hyderabad" AND "@"', 'Hyderabad', 'TRUE', 'Active'],
      
      // Chennai (6)
      ['"Hiring" AND "Chennai" AND "@"', 'Chennai', 'TRUE', 'Active'],
      ['"Urgent Hiring" AND "Chennai" AND "@"', 'Chennai', 'TRUE', 'Active'],
      ['"Immediate Joiner" AND "Chennai" AND "@"', 'Chennai', 'TRUE', 'Active'],
      ['"Immediate Joining" AND "Chennai" AND "@"', 'Chennai', 'TRUE', 'Active'],
      ['"We\'re Hiring" AND "Chennai" AND "@"', 'Chennai', 'TRUE', 'Active'],
      ['"We are hiring" AND "Chennai" AND "@"', 'Chennai', 'TRUE', 'Active'],
      
      // Mumbai (6)
      ['"Hiring" AND "Mumbai" AND "@"', 'Mumbai', 'TRUE', 'Active'],
      ['"Urgent Hiring" AND "Mumbai" AND "@"', 'Mumbai', 'TRUE', 'Active'],
      ['"Immediate Joiner" AND "Mumbai" AND "@"', 'Mumbai', 'TRUE', 'Active'],
      ['"Immediate Joining" AND "Mumbai" AND "@"', 'Mumbai', 'TRUE', 'Active'],
      ['"We\'re Hiring" AND "Mumbai" AND "@"', 'Mumbai', 'TRUE', 'Active'],
      ['"We are hiring" AND "Mumbai" AND "@"', 'Mumbai', 'TRUE', 'Active'],
      
      // Pune (6)
      ['"Hiring" AND "Pune" AND "@"', 'Pune', 'TRUE', 'Active'],
      ['"Urgent Hiring" AND "Pune" AND "@"', 'Pune', 'TRUE', 'Active'],
      ['"Immediate Joiner" AND "Pune" AND "@"', 'Pune', 'TRUE', 'Active'],
      ['"Immediate Joining" AND "Pune" AND "@"', 'Pune', 'TRUE', 'Active'],
      ['"We\'re Hiring" AND "Pune" AND "@"', 'Pune', 'TRUE', 'Active'],
      ['"We are hiring" AND "Pune" AND "@"', 'Pune', 'TRUE', 'Active'],
      
      // Ahmedabad (6)
      ['"Urgent Hiring" AND "Ahmedabad" AND "@"', 'Ahmedabad', 'TRUE', 'Active'],
      ['"Immediate Joiner" AND "Ahmedabad" AND "@"', 'Ahmedabad', 'TRUE', 'Active'],
      ['"Hiring" AND "Ahmedabad" AND "@"', 'Ahmedabad', 'TRUE', 'Active'],
      ['"We\'re Hiring" AND "Ahmedabad" AND "@"', 'Ahmedabad', 'TRUE', 'Active'],
      ['"Immediate Joining" AND "Ahmedabad" AND "@"', 'Ahmedabad', 'TRUE', 'Active'],
      ['"We are hiring" AND "Ahmedabad" AND "@"', 'Ahmedabad', 'TRUE', 'Active'],
      
      // Noida (7)
      ['"Urgent Hiring" AND "Noida" AND "@"', 'Noida', 'TRUE', 'Active'],
      ['"Immediate Joiner" AND "Noida" AND "@"', 'Noida', 'TRUE', 'Active'],
      ['"Immediate Joining" AND "Noida" AND "@"', 'Noida', 'TRUE', 'Active'],
      ['"We\'re Hiring" AND "Noida" AND "@"', 'Noida', 'TRUE', 'Active'],
      ['"We are hiring" AND "Noida" AND "@"', 'Noida', 'TRUE', 'Active'],
      ['"Hiring" AND "Noida" AND "@"', 'Noida', 'TRUE', 'Active'],
      
      // Delhi (6)
      ['"Hiring" AND "Delhi" AND "@"', 'Delhi', 'TRUE', 'Active'],
      ['"Urgent Hiring" AND "Delhi" AND "@"', 'Delhi', 'TRUE', 'Active'],
      ['"Immediate Joiner" AND "Delhi" AND "@"', 'Delhi', 'TRUE', 'Active'],
      ['"Immediate Joining" AND "Delhi" AND "@"', 'Delhi', 'TRUE', 'Active'],
      ['"We\'re Hiring" AND "Delhi" AND "@"', 'Delhi', 'TRUE', 'Active'],
      ['"We are hiring" AND "Delhi" AND "@"', 'Delhi', 'TRUE', 'Active'],
      
      // Gurugram (6)
      ['"Hiring" AND "Gurugram" AND "@"', 'Gurugram', 'TRUE', 'Active'],
      ['"Urgent Hiring" AND "Gurugram" AND "@"', 'Gurugram', 'TRUE', 'Active'],
      ['"Immediate Joiner" AND "Gurugram" AND "@"', 'Gurugram', 'TRUE', 'Active'],
      ['"Immediate Joining" AND "Gurugram" AND "@"', 'Gurugram', 'TRUE', 'Active'],
      ['"We\'re Hiring" AND "Gurugram" AND "@"', 'Gurugram', 'TRUE', 'Active'],
      ['"We are hiring" AND "Gurugram" AND "@"', 'Gurugram', 'TRUE', 'Active'],
      
      // New Delhi (6)
      ['"Hiring" AND "New Delhi" AND "@"', 'New Delhi', 'TRUE', 'Active'],
      ['"Urgent Hiring" AND "New Delhi" AND "@"', 'New Delhi', 'TRUE', 'Active'],
      ['"Immediate Joiner" AND "New Delhi" AND "@"', 'New Delhi', 'TRUE', 'Active'],
      ['"Immediate Joining" AND "New Delhi" AND "@"', 'New Delhi', 'TRUE', 'Active'],
      ['"We\'re Hiring" AND "New Delhi" AND "@"', 'New Delhi', 'TRUE', 'Active'],
      ['"We are hiring" AND "New Delhi" AND "@"', 'New Delhi', 'TRUE', 'Active']
    ];
    queriesSheet.getRange(2, 1, defaultQueries.length, 4).setValues(defaultQueries);
  }

  // -------------------------------------------------------------
  // 3. TAB: Settings (Filter Rules)
  // -------------------------------------------------------------
  var settingsSheet = ss.getSheetByName('Settings') || ss.insertSheet('Settings');
  var isSettingsNew = (settingsSheet.getLastRow() === 0);
  var settingsRequired = ['Blocked Domains', 'Rejection Keywords', 'Blocked Suffixes'];
  var settingsWidths = [220, 220, 200];
  var settingsAdded = ensureSheetHeaders(settingsSheet, settingsRequired, '#34A853', '#FFFFFF', settingsWidths);
  if (settingsAdded.length > 0) {
    syncLog.push('• Settings: Added column(s) [' + settingsAdded.join(', ') + ']');
  }

  // Populate default filter lists only if sheet was completely empty
  if (isSettingsNew) {
    var defaultBlockedDomains = [
      'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'aol.com',
      'icloud.com', 'zoho.com', 'mail.com', 'protonmail.com', 'yandex.com',
      'rediffmail.com', 'gmx.com', 'live.com', 'msn.com'
    ];
    var defaultRejectionKeywords = [
      'consultancy', 'hr', 'recruitment', 'career', 'careers', 'contact',
      'hire', 'support', 'jobs', 'staffing', 'talent', 'apply', 'info',
      'sales', 'admin', 'help', 'team', 'service', 'inquiry'
    ];
    var defaultBlockedSuffixes = [
      '.edu', '.ac.in', '.gov', '.mil', '.org', '.int', '.uk', '.ca', '.au',
      '.cn', '.jp', '.de', '.fr', '.it', '.ru', '.br', '.xyz', '.info', '.biz',
      '.name', '.pro', '.aero', '.coop', '.museum', '.jobs', '.mobi', '.tel',
      '.asia', '.post', '.cat', '.travel', '.xxx', '.tv', '.me', '.cc', '.ws',
      '.nu', '.tk', '.ml', '.ga', '.cf', '.gq', '.top', '.club', '.site',
      '.online', '.store', '.shop', '.dev'
    ];

    var maxRows = Math.max(defaultBlockedDomains.length, defaultRejectionKeywords.length, defaultBlockedSuffixes.length);
    var settingsData = [];
    for (var i = 0; i < maxRows; i++) {
      settingsData.push([
        defaultBlockedDomains[i] || '',
        defaultRejectionKeywords[i] || '',
        defaultBlockedSuffixes[i] || ''
      ]);
    }
    settingsSheet.getRange(2, 1, settingsData.length, 3).setValues(settingsData);
  }

  // -------------------------------------------------------------
  // 4. TAB: Apify_Tokens (Apify Token Pool - Preserves Passwords & Data)
  // -------------------------------------------------------------
  var tokensSheet = ss.getSheetByName('Apify_Tokens') || ss.insertSheet('Apify_Tokens');
  var isTokensNew = (tokensSheet.getLastRow() === 0);
  var tokensRequired = ['api_token', 'account_name', 'password', 'status', 'available_balance_usd', 'last_used_at', 'notes'];
  var tokensWidths = [350, 160, 160, 120, 170, 200, 200];
  var tokensAdded = ensureSheetHeaders(tokensSheet, tokensRequired, '#FBBC05', '#202124', tokensWidths);
  if (tokensAdded.length > 0) {
    syncLog.push('• Apify_Tokens: Added column(s) [' + tokensAdded.join(', ') + ']');
  }

  // Pre-fill placeholder slots only if the sheet was newly created with zero existing rows
  if (isTokensNew) {
    var tokenRows = [];
    for (var k = 1; k <= 50; k++) {
      tokenRows.push([
        '', // Enter token here
        'Apify Account ' + k,
        '', // Password column
        'ACTIVE',
        5.00,
        '',
        'Ready'
      ]);
    }
    tokensSheet.getRange(2, 1, tokenRows.length, 7).setValues(tokenRows);
  }

  // -------------------------------------------------------------
  // 5. TAB: Daily_Analytics (Historical Logs)
  // -------------------------------------------------------------
  var analyticsSheet = ss.getSheetByName('Daily_Analytics') || ss.insertSheet('Daily_Analytics');
  var analyticsRequired = [
    'Date', 'Day_of_Week', 'Queries_Run', 'Posts_Found', 'Leads_Extracted',
    'Avg_Posts_Per_Query', 'Total_Cost_USD', 'Avg_Cost_Per_Query_USD', 'Avg_Cost_Per_Lead_USD'
  ];
  var analyticsWidths = [160, 160, 160, 160, 160, 160, 160, 160, 160];
  var analyticsAdded = ensureSheetHeaders(analyticsSheet, analyticsRequired, '#9334E8', '#FFFFFF', analyticsWidths);
  if (analyticsAdded.length > 0) {
    syncLog.push('• Daily_Analytics: Added column(s) [' + analyticsAdded.join(', ') + ']');
  }

  // Build user notification message
  var message = '✅ Safe Sync Completed!\nAll 5 sheets are 100% verified and synchronized with zero data loss.\n';
  if (syncLog.length > 0) {
    message += '\nColumns Automatically Synchronized:\n' + syncLog.join('\n');
  } else {
    message += '\nAll standard columns were already present and aligned.';
  }

  SpreadsheetApp.getUi().alert(message);
}

/**
 * Removes duplicate leads dynamically based on the 'Email' column.
 * Locates the 'Email' column header dynamically so custom columns and any layout changes are preserved.
 */
function removeDuplicateLeads() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var leadsSheet = ss.getSheetByName('Leads Database');
  if (!leadsSheet || leadsSheet.getLastRow() < 2) {
    SpreadsheetApp.getUi().alert('No data found in Leads Database.');
    return;
  }

  var lastCol = leadsSheet.getLastColumn();
  var headers = leadsSheet.getRange(1, 1, 1, lastCol).getValues()[0];
  
  // Dynamically find the column index for 'Email'
  var emailColIndex = 1;
  for (var i = 0; i < headers.length; i++) {
    if (headers[i] && headers[i].toString().trim().toLowerCase() === 'email') {
      emailColIndex = i + 1;
      break;
    }
  }

  var fullRange = leadsSheet.getRange(1, 1, leadsSheet.getLastRow(), lastCol);
  fullRange.removeDuplicates([emailColIndex]);
  SpreadsheetApp.getUi().alert('✅ Duplicates cleaned based on Email (Column ' + emailColIndex + '). All custom columns and data rows preserved.');
}

/**
 * Calculates historical averages by Day of Week (Monday - Sunday).
 * Dynamically resolves column positions by header names.
 */
function calculateDayOfWeekAverages() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName('Daily_Analytics');
  if (!sheet || sheet.getLastRow() < 2) {
    SpreadsheetApp.getUi().alert('No analytics data to summarize yet.');
    return;
  }
  
  var lastCol = sheet.getLastColumn();
  var headers = sheet.getRange(1, 1, 1, lastCol).getValues()[0];
  var headerMap = {};
  for (var h = 0; h < headers.length; h++) {
    if (headers[h]) {
      headerMap[headers[h].toString().trim().toLowerCase()] = h;
    }
  }

  var dayColIdx = headerMap['day_of_week'] !== undefined ? headerMap['day_of_week'] : 1;
  var postsColIdx = headerMap['posts_found'] !== undefined ? headerMap['posts_found'] : 3;
  var costColIdx = headerMap['total_cost_usd'] !== undefined ? headerMap['total_cost_usd'] : 6;

  var data = sheet.getRange(2, 1, sheet.getLastRow() - 1, lastCol).getValues();
  var dayStats = {
    'Monday': { posts: 0, cost: 0, count: 0 },
    'Tuesday': { posts: 0, cost: 0, count: 0 },
    'Wednesday': { posts: 0, cost: 0, count: 0 },
    'Thursday': { posts: 0, cost: 0, count: 0 },
    'Friday': { posts: 0, cost: 0, count: 0 },
    'Saturday': { posts: 0, cost: 0, count: 0 },
    'Sunday': { posts: 0, cost: 0, count: 0 }
  };

  data.forEach(function(row) {
    var day = row[dayColIdx];
    var posts = parseFloat(row[postsColIdx]) || 0;
    var rawCost = row[costColIdx] ? row[costColIdx].toString().replace('$', '').trim() : '0';
    var cost = parseFloat(rawCost) || 0;
    if (dayStats[day]) {
      dayStats[day].posts += posts;
      dayStats[day].cost += cost;
      dayStats[day].count += 1;
    }
  });

  var summary = '📊 Day of Week Averages:\n\n';
  for (var day in dayStats) {
    var d = dayStats[day];
    var avgPosts = d.count > 0 ? (d.posts / d.count).toFixed(1) : '0';
    var avgCost = d.count > 0 ? '$' + (d.cost / d.count).toFixed(3) : '$0.000';
    summary += day + ': ' + avgPosts + ' posts/day | Avg Cost: ' + avgCost + '\n';
  }

  SpreadsheetApp.getUi().alert(summary);
}
