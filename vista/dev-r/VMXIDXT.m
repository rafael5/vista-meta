VMXIDXT ;vista-meta — tests for VMXIDX (no M test framework in the image)
 ;;1.0;VISTA-META;;
 ;RUNS IN: container, as vehu:  D EN^VMXIDXT
 ;Writes one line per check and a PASS/FAIL total.
 Q
 ;
EN ;@summary Run every VMXIDX check and print the total
 ;@test LOCS joins XINDEX's chunks; a real routine yields TAG+n
 N PASS,FAIL S (PASS,FAIL)=0
 D LOCSUNIT,LOCSREAL
 W !,"VMXIDXT: ",PASS," passed, ",FAIL," failed",!
 Q
 ;
EQ(GOT,WANT,WHAT) ;@summary Record one check as passed or failed
 ;@test helper for the checks below
 I GOT=WANT S PASS=PASS+1 W "  ok   ",WHAT,! Q
 S FAIL=FAIL+1 W "  FAIL ",WHAT,": got """,GOT,""" want """,WANT,"""",!
 Q
 ;
LOCSUNIT ;@summary LOCS joins the chunks of comma-terminated LAB+n text
 ;@test two chunks, one chunk, an absent reference
 K ^UTILITY($J,1,"ZZVMXT")
 S ^UTILITY($J,1,"ZZVMXT","X","DIC ",0)="EN+3,EN+7,"
 S ^UTILITY($J,1,"ZZVMXT","X","DIC ",1)="PROC,"
 S ^UTILITY($J,1,"ZZVMXT","X","XLFDT $$NOW",0)="START+12,"
 D EQ($$LOCS^VMXIDX("ZZVMXT","DIC "),"EN+3,EN+7,PROC","two chunks joined")
 D EQ($$LOCS^VMXIDX("ZZVMXT","XLFDT $$NOW"),"START+12","one location")
 D EQ($$LOCS^VMXIDX("ZZVMXT","NOPE "),"","absent ref")
 K ^UTILITY($J,1,"ZZVMXT")
 Q
 ;
LOCSREAL ;@summary A real routine yields its TAG+n call site
 ;@test PXRMASU calls $$OVERLAP^PXRMINDX at CLASS+16 (source line 20)
 N OK
 K ^UTILITY($J)
 D SETUP^VMXIDX
 S OK=$$PROC^VMXIDX("PXRMASU")
 D EQ(OK,1,"PXRMASU indexed")
 D EQ($$LOCS^VMXIDX("PXRMASU","PXRMINDX $$OVERLAP"),"CLASS+16","real call site")
 K ^UTILITY($J)
 Q
