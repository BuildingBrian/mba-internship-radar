// Internship Radar → Google Sheets tracker.
// 1. Make a new Google Sheet. 2. Extensions → Apps Script. 3. Replace everything with this file. Save.
// 4. Deploy → New deployment → type: Web app → Execute as: Me → Who has access: Anyone → Deploy.
// 5. Approve the access prompt, copy the Web app URL, and save it as RADAR_SHEETS_URL.
// Anyone with that URL can add rows to this sheet, so keep it private like a password.
function doPost(e) {
  const book = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = book.getSheetByName('Radar') || book.insertSheet('Radar');
  if (sheet.getLastRow() === 0) {
    sheet.appendRow(['Found', 'Score', 'Company', 'Role', 'Location', 'Posted', 'Notes from the posting', 'Link', 'Source', 'Status', 'My notes']);
    sheet.setFrozenRows(1);
    sheet.getRange('J2:J').setDataValidation(SpreadsheetApp.newDataValidation()
      .requireValueInList(['New', 'Interested', 'Applied', 'Interview', 'Offer', 'Not for me'], true).build());
  }
  const data = JSON.parse(e.postData.contents || '{}');
  const rows = (data.rows || []).map(r => [r.found, r.score, r.company, r.title, r.location, r.posted, r.flags, r.url, r.source, 'New', '']);
  if (rows.length) sheet.getRange(sheet.getLastRow() + 1, 1, rows.length, rows[0].length).setValues(rows);
  return ContentService.createTextOutput(JSON.stringify({ ok: true, added: rows.length })).setMimeType(ContentService.MimeType.JSON);
}
