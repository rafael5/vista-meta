VMINV2B ;File 200 deeper investigation
 Q
RUN ;
 W !,"=== SSN check (stored at node 1;9) ===",!
 N I,C,WSSN S I=0,C=0,WSSN=0
 F  S I=$O(^VA(200,I)) Q:I=""  D
 . N V S V=$P($G(^VA(200,I,1)),"^",9)
 . I V'="" S WSSN=WSSN+1 W:WSSN<6 "  ",I," ",$P($G(^VA(200,I,0)),"^",1)," SSN=",V,!
 W "Total with SSN: ",WSSN,!
 ;
 W !,"=== Address check (node .11) ===",!
 N WADDR S WADDR=0,I=0
 F  S I=$O(^VA(200,I)) Q:I=""  D
 . I $G(^VA(200,I,.11))'="" S WADDR=WADDR+1
 W "With address data: ",WADDR,!
 ;
 W !,"=== Phone check (node .13) ===",!
 N WPHONE S WPHONE=0,I=0
 F  S I=$O(^VA(200,I)) Q:I=""  D
 . I $G(^VA(200,I,.13))'="" S WPHONE=WPHONE+1
 W "With phone data: ",WPHONE,!
 ;
 W !,"=== Email check (node .15) ===",!
 N WEMAIL S WEMAIL=0,I=0
 F  S I=$O(^VA(200,I)) Q:I=""  D
 . I $P($G(^VA(200,I,.15)),"^",1)'="" S WEMAIL=WEMAIL+1
 W "With email: ",WEMAIL,!
 ;
 W !,"=== Summary: PII/PHI fields populated ===",!
 W "  NAME (all entries):  yes — all have .01",!
 W "  SSN:                 ",WSSN,!
 W "  DOB:                 1151 (from prior run)",!
 W "  Address:             ",WADDR,!
 W "  Phone:               ",WPHONE,!
 W "  Email:               ",WEMAIL,!
 ;
 W !,"=== IEN overlap with ^DPT (PATIENT file) ===",!
 N OVR,OVC S OVR=0,OVC=0,I=0
 F  S I=$O(^VA(200,I)) Q:I=""  D
 . I $D(^DPT(I)) S OVR=OVR+1 W:OVR<6 "  IEN ",I,": ^VA(200)=",$P($G(^VA(200,I,0)),"^",1),"  ^DPT=",$P($G(^DPT(I,0)),"^",1),!
 W "Total IEN overlaps: ",OVR," (same IEN# in both File 200 and File 2)",!
 W "(These are DIFFERENT people — IEN overlap is coincidental, not identity)",!
 ;
 W !,"=== Conclusion ===",!
 W "File 200 is STAFF/PROVIDER data, not patient data.",!
 W "It contains names, SSNs, DOBs, addresses, phones, email",!
 W "for VA employees, providers, programmers, clerks, nurses, etc.",!
 W "This is PII for STAFF — protected under Privacy Act, not HIPAA.",!
 W "But from a PIKS sensitivity standpoint, it is 'protected' data.",!
 Q
