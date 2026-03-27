import pymupdf

pdf = pymupdf.open('GeM-Bidding-7176127.pdf')

print(pdf[1].get_textpage().extractText())