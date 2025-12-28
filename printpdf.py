import pdfkit

input_html = '/Users/zeenlong/Desktop/Automation_Test/Build_Framework/z_cytest-main/log/report_20251128_145126.html'
output_pdf = '/Users/zeenlong/Desktop/Automation_Test/Build_Framework/z_cytest-main/log/report_20251128_145126.pdf'

options = {
    'enable-local-file-access': None,
    'page-size': 'A4',
    'encoding': "UTF-8",
    'print-media-type': None
}
pdfkit.from_file(input_html, output_pdf, options=options)