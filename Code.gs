/**
 * Google Apps Script for LinkedIn Leads CRM & Apify Multi-Token Pool (Safe-Sync & Non-Destructive)
 * 
 * Key Features:
 * - SAFE & NON-DESTRUCTIVE: Never deletes your existing sheets, custom columns, or data rows.
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
 * Non-destructive setup: Checks and creates any missing sheets or headers.
 * Never deletes existing data, tokens, passwords, queries, or custom columns.
 */
function safeSyncSheets() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();

  // -------------------------------------------------------------
  // 1. TAB: Leads Database (Strict 5 Base Columns + Custom Columns)
  // -------------------------------------------------------------
  var leadsSheet = ss.getSheetByName('Leads Database');
  if (!leadsSheet) {
    leadsSheet = ss.insertSheet('Leads Database');
  }
  
  if (leadsSheet.getLastRow() === 0) {
    var leadsHeaders = [['Email', 'Domain', 'Phone Number', 'Name', 'Query']];
    leadsSheet.getRange(1, 1, 1, 5).setValues(leadsHeaders);
    var leadsHeaderRange = leadsSheet.getRange(1, 1, 1, 5);
    leadsHeaderRange.setBackground('#1A73E8')
                    .setFontColor('#FFFFFF')
                    .setFontWeight('bold')
                    .setHorizontalAlignment('center');
    leadsSheet.setFrozenRows(1);
    leadsSheet.setColumnWidth(1, 260); // Email
    leadsSheet.setColumnWidth(2, 180); // Domain
    leadsSheet.setColumnWidth(3, 170); // Phone Number
    leadsSheet.setColumnWidth(4, 200); // Name
    leadsSheet.setColumnWidth(5, 300); // Query
  }

  // -------------------------------------------------------------
  // 2. TAB: Queries (Search Queries Managed in Google Sheets)
  // -------------------------------------------------------------
  var queriesSheet = ss.getSheetByName('Queries');
  if (!queriesSheet) {
    queriesSheet = ss.insertSheet('Queries');
  }

  if (queriesSheet.getLastRow() === 0) {
    var queriesHeaders = [['Query', 'City', 'Enabled', 'Notes']];
    queriesSheet.getRange(1, 1, 1, 4).setValues(queriesHeaders);

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

    var queriesHeaderRange = queriesSheet.getRange(1, 1, 1, 4);
    queriesHeaderRange.setBackground('#009688')
                      .setFontColor('#FFFFFF')
                      .setFontWeight('bold')
                      .setHorizontalAlignment('center');
    queriesSheet.setFrozenRows(1);
    queriesSheet.setColumnWidth(1, 380); // Query
    queriesSheet.setColumnWidth(2, 150); // City
    queriesSheet.setColumnWidth(3, 100); // Enabled
    queriesSheet.setColumnWidth(4, 150); // Notes
  }

  // -------------------------------------------------------------
  // 3. TAB: Settings (Filter Rules)
  // -------------------------------------------------------------
  var settingsSheet = ss.getSheetByName('Settings');
  if (!settingsSheet) {
    settingsSheet = ss.insertSheet('Settings');
  }

  if (settingsSheet.getLastRow() === 0) {
    var settingsHeaders = [['Blocked Domains', 'Rejection Keywords', 'Blocked Suffixes']];
    settingsSheet.getRange(1, 1, 1, 3).setValues(settingsHeaders);
    
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

    var settingsHeaderRange = settingsSheet.getRange(1, 1, 1, 3);
    settingsHeaderRange.setBackground('#34A853')
                       .setFontColor('#FFFFFF')
                       .setFontWeight('bold')
                       .setHorizontalAlignment('center');
    settingsSheet.setFrozenRows(1);
    settingsSheet.setColumnWidth(1, 220);
    settingsSheet.setColumnWidth(2, 220);
    settingsSheet.setColumnWidth(3, 200);
  }

  // -------------------------------------------------------------
  // 4. TAB: Apify_Tokens (Apify Token Pool - Preserves Passwords & Data)
  // -------------------------------------------------------------
  var tokensSheet = ss.getSheetByName('Apify_Tokens');
  if (!tokensSheet) {
    tokensSheet = ss.insertSheet('Apify_Tokens');
  }

  if (tokensSheet.getLastRow() === 0) {
    var tokenHeaders = [['api_token', 'account_name', 'password', 'status', 'available_balance_usd', 'last_used_at', 'notes']];
    tokensSheet.getRange(1, 1, 1, 7).setValues(tokenHeaders);

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

    var tokensHeaderRange = tokensSheet.getRange(1, 1, 1, 7);
    tokensHeaderRange.setBackground('#FBBC05')
                     .setFontColor('#202124')
                     .setFontWeight('bold')
                     .setHorizontalAlignment('center');
    tokensSheet.setFrozenRows(1);
    tokensSheet.setColumnWidth(1, 350);
    tokensSheet.setColumnWidth(2, 160);
    tokensSheet.setColumnWidth(3, 160);
    tokensSheet.setColumnWidth(4, 120);
    tokensSheet.setColumnWidth(5, 170);
    tokensSheet.setColumnWidth(6, 200);
    tokensSheet.setColumnWidth(7, 200);
  }

  // -------------------------------------------------------------
  // 5. TAB: Daily_Analytics (Historical Logs)
  // -------------------------------------------------------------
  var analyticsSheet = ss.getSheetByName('Daily_Analytics');
  if (!analyticsSheet) {
    analyticsSheet = ss.insertSheet('Daily_Analytics');
  }

  if (analyticsSheet.getLastRow() === 0) {
    var analyticsHeaders = [[
      'Date', 'Day_of_Week', 'Queries_Run', 'Posts_Found', 'Leads_Extracted',
      'Avg_Posts_Per_Query', 'Total_Cost_USD', 'Avg_Cost_Per_Query_USD', 'Avg_Cost_Per_Lead_USD'
    ]];
    analyticsSheet.getRange(1, 1, 1, 9).setValues(analyticsHeaders);
    var analyticsHeaderRange = analyticsSheet.getRange(1, 1, 1, 9);
    analyticsHeaderRange.setBackground('#9334E8')
                        .setFontColor('#FFFFFF')
                        .setFontWeight('bold')
                        .setHorizontalAlignment('center');
    analyticsSheet.setFrozenRows(1);
    for (var c = 1; c <= 9; c++) {
      analyticsSheet.setColumnWidth(c, 160);
    }
  }

  SpreadsheetApp.getUi().alert('✅ Safe Sync Completed! All 5 tabs (Leads, Queries, Settings, Apify_Tokens, Analytics) are active.');
}

/**
 * Removes duplicate emails from Leads Database (Column A) while preserving all other custom columns.
 */
function removeDuplicateLeads() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var leadsSheet = ss.getSheetByName('Leads Database');
  if (!leadsSheet || leadsSheet.getLastRow() < 2) {
    SpreadsheetApp.getUi().alert('No data found in Leads Database.');
    return;
  }
  var fullRange = leadsSheet.getRange(1, 1, leadsSheet.getLastRow(), leadsSheet.getLastColumn());
  fullRange.removeDuplicates([1]);
  SpreadsheetApp.getUi().alert('✅ Duplicates cleaned based on Email (Column A). All other columns preserved.');
}

/**
 * Calculates historical averages by Day of Week (Monday - Sunday)
 */
function calculateDayOfWeekAverages() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName('Daily_Analytics');
  if (!sheet || sheet.getLastRow() < 2) {
    SpreadsheetApp.getUi().alert('No analytics data to summarize yet.');
    return;
  }
  
  var data = sheet.getRange(2, 1, sheet.getLastRow() - 1, Math.min(sheet.getLastColumn(), 9)).getValues();
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
    var day = row[1];
    var posts = parseFloat(row[3]) || 0;
    var cost = parseFloat(row[6]) || 0;
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
