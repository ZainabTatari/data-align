"""Hand-written expectations, derived by reasoning from the planted defects in fixtures.py
(NOT generated from engine output). If the engine disagrees, one of the two is wrong and must be investigated."""
DEFECTIVE_FAIL = set("""R01 R02 K01 K02 K03 M03 F01 F02 F03 Q01 Q02 Q03 Q04 A01 A02 A03 H01 H02 T01 T02 T03 P01 N01
B01 B02 B03 B04 B05 D01 D02 D03 PII02 PR01 PR03 RI01 RI02 RI03 E01 E04 CDC01 CDC02 CDC03 CDC04 CDC05
SE01 SE02 SE03 FE01 FE02 CP04""".split())
DEFECTIVE_REVIEW = {"M04", "L02"}
NOT_TESTED_ALWAYS = {"T04", "D04", "PF04", "CP03"}      # optional cases with nothing configured / not measurable
CLEAN_NOT_TESTED = NOT_TESTED_ALWAYS | {"SE03"}          # SE03 needs a previous run
