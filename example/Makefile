# This work is dedicated to the public domain.

# Basic settings

toolsdir = ..

# `make` targets are:
#
#        all - the default; create {cv,pubs}.{pdf,html}
#    summary - summarize entries
# update-ads - update ADS citation counts
#      clean - delete generated files

# Settings that probably won't need to be changed:

driver = $(toolsdir)/wltool
infos = $(wildcard *.txt)

# Rules:

all: cv.pdf pubs.pdf cv.html pubs.html

cv.tex: $(driver) cv.tmpl.tex $(infos)
	python $< latex cv.tmpl.tex >$@.new && mv -f $@.new $@

pubs.tex: $(driver) pubs.tmpl.tex $(infos)
	python $< latex pubs.tmpl.tex >$@.new && mv -f $@.new $@

cv.html: $(driver) cv.tmpl.html $(infos)
	python $< html cv.tmpl.html >$@.new && mv -f $@.new $@

pubs.html: $(driver) pubs.tmpl.html $(infos)
	python $< html pubs.tmpl.html >$@.new && mv -f $@.new $@

summary: $(infos)
	python $(driver) summarize

update-ads:
	python $(driver) update-cites

clean:
	-rm -f *.aux *.log *.log2 *.out cv.html cv.pdf cv.tex pubs.html pubs.pdf pubs.tex

%.pdf: %.tex
	@echo + making $@ -- error messages are in $*.log2 if anything goes wrong
	pdflatex $< >$*.log2
	pdflatex $< >$*.log2


# clear default make rules:
.SUFFIXES:
