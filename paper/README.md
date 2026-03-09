# Course Report

This directory contains the course-version final report based only on the current public repository contents.

Files:

- `course_report_for_course.tex`: main report source
- `references.bib`: bibliography entries used by the report
- `neurips_2025.sty`: local copy of the NeurIPS 2025 style file used by the report

Build example:

```bash
cd paper
pdflatex course_report_for_course.tex
bibtex course_report_for_course
pdflatex course_report_for_course.tex
pdflatex course_report_for_course.tex
```
