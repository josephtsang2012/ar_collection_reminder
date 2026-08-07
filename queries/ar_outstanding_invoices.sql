-- Database: GDB_01_POLY1
-- As of a specific date (@ASOFDAY) in this format, like 'YYYY-MM-DD HH:MM:SS'
-- Refactored and simplified AR Aging SQL for improved readability and maintainability

DECLARE @ASOFDAY DATETIME = GETDATE();
GO
/*
================================================================================
A. Create a temporary table to hold invoices that are not shipped
================================================================================
*/
IF OBJECT_ID('tempdb..#Inv_not_shipped') IS NOT NULL DROP TABLE #Inv_not_shipped;

SELECT DISTINCT LTRIM(RTRIM(IH.USER_DOC)) AS USER_DOC
INTO #Inv_not_shipped
FROM INV_HDR IH
    LEFT JOIN INV_LINE IL ON IH.DOC_NO = IL.DOC_NO
WHERE IH.COMPANYNO in (1, 2)
    AND IH.HOUS_AIRBILL = '' AND IH.MAST_AIRBILL = ''
    AND IL.UNITP <> 0 AND IL.UNITP IS NOT NULL;
GO
/*
================================================================================
1. Payment Aggregation for Normal Invoices (Excludes Pre-payment/RMA)
================================================================================
*/
CREATE OR ALTER VIEW dbo.AR_OUTSTANDING_INVOICES
AS
WITH
    PaymentAgg
    AS
    (
        SELECT
            PAY_DOC_NO,
            PAY_DOC_CATEGORY,
            DOC_STATUS AS P_DOC_STATUS,
            SUM(CASE WHEN DOC_STATUS <> 11 THEN ISNULL(AMOUNT, 0) ELSE 0 END) AS TotalAmount,
            SUM(CASE WHEN DOC_STATUS = 11 THEN ISNULL(ORIG_NETAMOUNT, 0) ELSE 0 END) AS TotalVoidAmount,
            SUM(CASE WHEN DOC_STATUS <>
             11 THEN ISNULL(C_AMOUNT, 0) ELSE 0 END) AS TotalCAmount,
            SUM(CASE WHEN DOC_STATUS = 11 THEN ISNULL(C_ORIG_NETAMOUNT, 0) ELSE 0 END) AS TotalCVoidAmount
        FROM VIEW_CUSTOMER_PAYMENT
        WHERE PERIOD_DATE <= @ASOFDAY AND PERIOD_DATE IS NOT NULL
        GROUP BY PAY_DOC_NO, PAY_DOC_CATEGORY, DOC_STATUS
    ),

    /*
================================================================================
2. Invoice Balances (Normal Invoices)
================================================================================
*/
    InvoiceBalances
    AS
    (
        SELECT
            V.*,
            LTRIM(RTRIM(V.USER_DOC)) AS USER_DOC_trim,
            ROUND(ISNULL(V.DOC_TOTAL, 0) - (ISNULL(PA.TotalAmount, 0) + ISNULL(PA.TotalVoidAmount, 0)), 2) AS OPEN_BALANCE,
            ROUND(ISNULL(V.C_DOC_TOTAL, 0) - (ISNULL(PA.TotalCAmount, 0) + ISNULL(PA.TotalCVoidAmount, 0)), 2) AS C_OPEN_BALANCE
        FROM VIEW_CUSTOMER_INV_AS_OF V
            LEFT JOIN PaymentAgg PA
            ON LTRIM(RTRIM(V.DOC_NO)) = LTRIM(RTRIM(PA.PAY_DOC_NO))
                AND V.DOC_CATEGORY = PA.PAY_DOC_CATEGORY
                AND V.DOC_STATUS = PA.P_DOC_STATUS
    ),

    /*
================================================================================
3. Filtered Normal Invoices (Non-zero Balances)
================================================================================
*/
    FilteredInvoices
    AS
    (
        SELECT *
        FROM InvoiceBalances
        WHERE (
        ((ARAP_CURENCY_STATE = 0 AND OPEN_BALANCE > 0)
            OR (ARAP_CURENCY_STATE = 1 AND C_OPEN_BALANCE > 0))
            AND (DOC_STATUS <> 11 OR (DOC_STATUS = 11 AND UPDATED_DTE > @ASOFDAY))
            AND INV_DATE <= @ASOFDAY
    )
    ),

    /*
================================================================================
4. Payment Totals for Outstanding Invoices
================================================================================
*/
    InvoicePayments
    AS
    (
        SELECT
            FI.USER_DOC_trim,
            SUM(CL.AMOUNT) AS TotalPaid
        FROM FilteredInvoices FI
            LEFT JOIN INV_HDR IH ON FI.USER_DOC = IH.USER_DOC
            LEFT JOIN CHECK_LINE CL ON CL.PAY_DOC_CATEGORY = 'IV'
                AND CL.PAY_DOC_NO = IH.DOC_NO
                AND CL.DOC_TYPE = 'AR'
        WHERE CL.PAY_APPLY <= @ASOFDAY
        GROUP BY FI.USER_DOC_trim
    ),

    /*
================================================================================
5. Aging Buckets for Positive Invoices
================================================================================
*/
    AgingPositive
    AS
    (
        SELECT
            FI.USER_DOC_trim,
            FI.LINE,
            OA = ROUND(FI.DOC_TOTAL - ISNULL(IP.TotalPaid, 0), 2),
            B_00_30 = CASE WHEN DATEDIFF(DAY, FI.POST_GL_DATE, @ASOFDAY) BETWEEN 0 AND 30 THEN ROUND(FI.DOC_TOTAL - ISNULL(IP.TotalPaid, 0), 2) ELSE 0 END,
            B_31_60 = CASE WHEN DATEDIFF(DAY, FI.POST_GL_DATE, @ASOFDAY) BETWEEN 31 AND 60 THEN ROUND(FI.DOC_TOTAL - ISNULL(IP.TotalPaid, 0), 2) ELSE 0 END,
            B_61_90 = CASE WHEN DATEDIFF(DAY, FI.POST_GL_DATE, @ASOFDAY) BETWEEN 61 AND 90 THEN ROUND(FI.DOC_TOTAL - ISNULL(IP.TotalPaid, 0), 2) ELSE 0 END,
            B_91_180 = CASE WHEN DATEDIFF(DAY, FI.POST_GL_DATE, @ASOFDAY) BETWEEN 91 AND 180 THEN ROUND(FI.DOC_TOTAL - ISNULL(IP.TotalPaid, 0), 2) ELSE 0 END,
            B_181_360 = CASE WHEN DATEDIFF(DAY, FI.POST_GL_DATE, @ASOFDAY) BETWEEN 181 AND 360 THEN ROUND(FI.DOC_TOTAL - ISNULL(IP.TotalPaid, 0), 2) ELSE 0 END,
            B_181_360 = CASE WHEN DATEDIFF(DAY, FI.POST_GL_DATE, @ASOFDAY) BETWEEN 181 AND 360 THEN ROUND(FI.DOC_TOTAL - ISNULL(IP.TotalPaid, 0), 2) ELSE 0 END,
            B_OVER_360 = CASE WHEN DATEDIFF(DAY, FI.POST_GL_DATE, @ASOFDAY) > 360 THEN ROUND(FI.DOC_TOTAL - ISNULL(IP.TotalPaid, 0), 2) ELSE 0 END
        FROM FilteredInvoices FI
            LEFT JOIN InvoicePayments IP ON FI.USER_DOC_trim = IP.USER_DOC_trim
    ),

    /*
================================================================================
6. Negative Invoice (Pre-payment/RMA) Processing
================================================================================
*/
    NegBase
    AS
    (
        SELECT
            ACCTNO, DOC_NO, LINE, USER_DOC, DOC_DATE, DOC_TOTAL, C_DOC_TOTAL, VOID_TOTAL, C_VOID_TOTAL, CHANGE_DATE,
            SUM(CHANGE_AMOUNT) AS CHANGE_AMOUNT, SUM(C_CHANGE_AMOUNT) AS C_CHANGE_AMOUNT
        FROM (
        -- Refunds
                        SELECT
                    LTRIM(RTRIM(ca.ACCTNO)) AS ACCTNO,
                    LTRIM(RTRIM(ca.DOC_NO)) AS DOC_NO,
                    LTRIM(RTRIM(ca.LINE)) AS LINE,
                    LTRIM(RTRIM(ca.USER_DOC)) AS USER_DOC,
                    ca.DOC_DATE, ca.DOC_TOTAL, ca.C_DOC_TOTAL, ca.VOID_TOTAL, ca.C_VOID_TOTAL,
                    arp.DOC_DATE AS CHANGE_DATE,
                    arp.DOC_TOTAL AS CHANGE_AMOUNT,
                    arp.C_DOC_TOTAL AS C_CHANGE_AMOUNT
                FROM VIEW_CREDIT_APPLY ca
                    INNER JOIN ACCOUNT_AR_AP arp
                    ON LTRIM(RTRIM(ca.ACCTNO)) = LTRIM(RTRIM(arp.ACCTNO))
                        AND LTRIM(RTRIM(ca.DOC_NO)) = LTRIM(RTRIM(arp.DOC_NO))
                        AND LTRIM(RTRIM(ca.LINE)) = LTRIM(RTRIM(arp.LINE))
                        AND LTRIM(RTRIM(ca.USER_DOC)) = LTRIM(RTRIM(arp.USER_DOC))
                        AND arp.AR_AP = 'AP'
                WHERE ca.DOC_TOTAL < 0 AND ca.DOC_DATE <= @ASOFDAY
            UNION ALL
                -- Cheque applies
                SELECT
                    LTRIM(RTRIM(ca.ACCTNO)), LTRIM(RTRIM(ca.DOC_NO)), LTRIM(RTRIM(ca.LINE)), LTRIM(RTRIM(ca.USER_DOC)),
                    ca.DOC_DATE, ca.DOC_TOTAL, ca.C_DOC_TOTAL, ca.VOID_TOTAL, ca.C_VOID_TOTAL,
                    COALESCE(ch.CHECK_DATE, ca.UPDATED_DTE),
                    ISNULL(ch.APPLIED, 0), ISNULL(ch.C_APPLIED, 0)
                FROM VIEW_CREDIT_APPLY ca
                    LEFT JOIN CHECK_HDR ch
                    ON LTRIM(RTRIM(ca.ACCTNO)) = LTRIM(RTRIM(ch.ACCTNO))
                        AND LTRIM(RTRIM(ca.DOC_NO)) = LTRIM(RTRIM(ch.CRDT_DOC_NO))
                        AND LTRIM(RTRIM(ca.LINE)) = LTRIM(RTRIM(ch.CRDT_LINE))
                WHERE ca.DOC_TOTAL < 0 AND ca.DOC_DATE <= @ASOFDAY
    ) raw
        GROUP BY ACCTNO, DOC_NO, LINE, USER_DOC, DOC_DATE, DOC_TOTAL, C_DOC_TOTAL, VOID_TOTAL, C_VOID_TOTAL, CHANGE_DATE
    ),
    NegBaseTag
    AS
    (
        SELECT
            *,
            SUM(CHANGE_AMOUNT) OVER (PARTITION BY ACCTNO, DOC_NO, LINE, USER_DOC, DOC_DATE ORDER BY (CASE WHEN CHANGE_DATE IS NULL THEN 1 ELSE 0 END), CHANGE_DATE ASC, CHANGE_AMOUNT DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS CUMULATIVE_PAID,
            SUM(C_CHANGE_AMOUNT) OVER (PARTITION BY ACCTNO, DOC_NO, LINE, USER_DOC, DOC_DATE ORDER BY (CASE WHEN CHANGE_DATE IS NULL THEN 1 ELSE 0 END), CHANGE_DATE ASC, CHANGE_AMOUNT DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS C_CUMULATIVE_PAID,
            CASE 
            WHEN (CHANGE_DATE > @ASOFDAY AND CHANGE_DATE IS NOT NULL) THEN 'after as of day'
            WHEN (CHANGE_DATE <= @ASOFDAY AND CHANGE_DATE IS NOT NULL) THEN 'on/ before as of day'
            ELSE NULL
        END AS ROW_TAG
        FROM NegBase
    ),
    NegRowNum
    AS
    (
                    SELECT *,
                ROW_NUMBER() OVER (PARTITION BY ACCTNO, DOC_NO, LINE, USER_DOC, DOC_DATE ORDER BY CHANGE_DATE ASC, CHANGE_AMOUNT DESC) AS rn,
                'after' AS row_type
            FROM NegBaseTag
            WHERE ROW_TAG = 'after as of day'
        UNION ALL
            SELECT *,
                ROW_NUMBER() OVER (PARTITION BY ACCTNO, DOC_NO, LINE, USER_DOC, DOC_DATE ORDER BY CHANGE_DATE DESC, CHANGE_AMOUNT DESC) AS rn,
                'onbefore' AS row_type
            FROM NegBaseTag
            WHERE ROW_TAG = 'on/ before as of day'
    ),
    NegFinal
    AS
    (
        SELECT
            nbt.*,
            n1.rn AS rn_after,
            n2.rn AS rn_onbefore,
            (nbt.DOC_TOTAL - nbt.VOID_TOTAL + nbt.CUMULATIVE_PAID) AS BALANCE,
            (nbt.C_DOC_TOTAL - nbt.C_VOID_TOTAL + nbt.C_CUMULATIVE_PAID) AS C_BALANCE,
            (nbt.DOC_TOTAL - nbt.VOID_TOTAL + nbt.CUMULATIVE_PAID - nbt.CHANGE_AMOUNT) AS BALANCE_BEFORE_CHANGE,
            (nbt.C_DOC_TOTAL - nbt.C_VOID_TOTAL + nbt.C_CUMULATIVE_PAID - nbt.C_CHANGE_AMOUNT) AS C_BALANCE_BEFORE_CHANGE
        FROM NegBaseTag nbt
            LEFT JOIN (SELECT *
            FROM NegRowNum
            WHERE row_type = 'after') n1
            ON nbt.ACCTNO = n1.ACCTNO AND nbt.DOC_NO = n1.DOC_NO AND nbt.LINE = n1.LINE AND nbt.USER_DOC = n1.USER_DOC AND nbt.DOC_DATE = n1.DOC_DATE AND nbt.CHANGE_DATE = n1.CHANGE_DATE
            LEFT JOIN (SELECT *
            FROM NegRowNum
            WHERE row_type = 'onbefore') n2
            ON nbt.ACCTNO = n2.ACCTNO AND nbt.DOC_NO = n2.DOC_NO AND nbt.LINE = n2.LINE AND nbt.USER_DOC = n2.USER_DOC AND nbt.DOC_DATE = n2.DOC_DATE AND nbt.CHANGE_DATE = n2.CHANGE_DATE
    ),
    NegPriority
    AS
    (
        SELECT *,
            CASE 
            WHEN rn_after = 1 THEN 1
            WHEN rn_onbefore = 1 THEN 2
            WHEN rn_after IS NULL AND rn_onbefore IS NULL AND ROW_TAG IS NULL AND BALANCE_BEFORE_CHANGE <> 0 THEN 3
            ELSE 100
        END AS sel_priority
        FROM NegFinal
    ),
    NegSelected
    AS
    (
        SELECT *,
            CASE WHEN ROW_NUMBER() OVER (
            PARTITION BY ACCTNO, DOC_NO, LINE, USER_DOC, DOC_DATE
            ORDER BY sel_priority, CHANGE_DATE ASC, CHANGE_AMOUNT DESC
        ) = 1 AND sel_priority < 100 THEN 'selected row as of day' ELSE NULL END AS row_selected
        FROM NegPriority
    ),
    NegInvoices
    AS
        SELECT *
        FROM NegSelected
        WHERE row_selected = 'selected row as of day'
            AND (
            (ROW_TAG = 'after as of day' AND BALANCE_BEFORE_CHANGE < 0)
            OR (ROW_TAG = 'on/ before as of day' AND BALANCE < 0)
            OR ROW_TAG IS NULL
        )
    ),
    FilteredNegInvoices
    AS
    (
        SELECT
            V.*,
            LTRIM(RTRIM(V.USER_DOC)) AS USER_DOC_trim,
            OPEN_BALANCE = CASE 
            WHEN ROW_TAG = 'after as of day' THEN ROUND(NI.BALANCE_BEFORE_CHANGE, 2)
            WHEN ROW_TAG = 'on/ before as of day' THEN ROUND(NI.BALANCE, 2)
            WHEN ROW_TAG IS NULL THEN ROUND(NI.BALANCE_BEFORE_CHANGE, 2)
            ELSE ROUND(ISNULL(V.DOC_TOTAL, 0), 2)
        END
        FROM NegInvoices NI
            INNER JOIN VIEW_CUSTOMER_INV_AS_OF V
            ON LTRIM(RTRIM(V.USER_DOC)) = NI.USER_DOC AND V.LINE = NI.LINE
        WHERE V.DOC_TOTAL < 0
    ),
    AgingNegative
    AS
    (
        SELECT
            FNI.USER_DOC_trim,
            FNI.LINE,
            OA = ROUND(FNI.OPEN_BALANCE, 2),
            B_00_30 = CASE WHEN DATEDIFF(DAY, FNI.POST_GL_DATE, @ASOFDAY) BETWEEN 0 AND 30 THEN ROUND(FNI.OPEN_BALANCE, 2) ELSE 0 END,
            B_31_60 = CASE WHEN DATEDIFF(DAY, FNI.POST_GL_DATE, @ASOFDAY) BETWEEN 31 AND 60 THEN ROUND(FNI.OPEN_BALANCE, 2) ELSE 0 END,
            B_61_90 = CASE WHEN DATEDIFF(DAY, FNI.POST_GL_DATE, @ASOFDAY) BETWEEN 61 AND 90 THEN ROUND(FNI.OPEN_BALANCE, 2) ELSE 0 END,
            B_91_180 = CASE WHEN DATEDIFF(DAY, FNI.POST_GL_DATE, @ASOFDAY) BETWEEN 91 AND 180 THEN ROUND(FNI.OPEN_BALANCE, 2) ELSE 0 END,
            B_181_360 = CASE WHEN DATEDIFF(DAY, FNI.POST_GL_DATE, @ASOFDAY) BETWEEN 181 AND 360 THEN ROUND(FNI.OPEN_BALANCE, 2) ELSE 0 END,
            B_OVER_360 = CASE WHEN DATEDIFF(DAY, FNI.POST_GL_DATE, @ASOFDAY) > 360 THEN ROUND(FNI.OPEN_BALANCE, 2) ELSE 0 END
        FROM FilteredNegInvoices FNI
        WHERE ROUND(FNI.OPEN_BALANCE, 2) < 0
    ),

    /*
================================================================================
7. Combine All Invoices and Aging Buckets
================================================================================
*/
    AllInvoices
    AS
    (
                    SELECT
                COMPANYNO, SUBC, ACCTNO, DOC_NO, LINE, USER_DOC, DOC_DATE, DOC_CATEGORY, DOC_STATUS, PARENT_DOCCATEGORY, PARENT_DOC_NO, SMAN1_CODE, [NAME], INV_DATE, INV_DUE, DOC_TOTAL, C_DOC_TOTAL,
                UPDATED_DTE, POST_GL_DATE, ARAP_CURENCY_STATE, USER_DOC_trim, OPEN_BALANCE
            FROM FilteredInvoices
        UNION ALL
            SELECT
                COMPANYNO, SUBC, ACCTNO, DOC_NO, LINE, USER_DOC, DOC_DATE, DOC_CATEGORY, DOC_STATUS, PARENT_DOCCATEGORY, PARENT_DOC_NO, SMAN1_CODE, [NAME], INV_DATE, INV_DUE, DOC_TOTAL, C_DOC_TOTAL,
                UPDATED_DTE, POST_GL_DATE, ARAP_CURENCY_STATE, USER_DOC_trim, OPEN_BALANCE
            FROM FilteredNegInvoices
    ),
    AllAging
    AS
    (
                    SELECT USER_DOC_trim, LINE, OA, B_00_30, B_31_60, B_61_90, B_91_180, B_181_360, B_OVER_360
            FROM AgingPositive
        UNION ALL
            SELECT USER_DOC_trim, LINE, OA, B_00_30, B_31_60, B_61_90, B_91_180, B_181_360, B_OVER_360
            FROM AgingNegative
    )

/*
================================================================================
8. Final Output
================================================================================
*/

SELECT
    GETDATE() 'As of Day',
    CD.COMPANYNO AS [Company No.],
    CD.SUBC,
    CONCAT(LTRIM(RTRIM(CD.SUBC)), LTRIM(RTRIM(CD.ACCTNO))) AS [KeyCustCode],
    CD.[NAME] AS [Customer Name],
    CTS.SEARCH10 AS [SalesRegion],
    CD.ACCTNO AS [Account No.],
    CD.USER_DOC_trim AS [Invoice No.],
    CASE
        WHEN CD.DOC_STATUS = 1 THEN 'Pending'
        WHEN CD.DOC_STATUS = 11 THEN 'Void'
        WHEN CD.DOC_STATUS = 13 THEN 'Posted(GL)'
        WHEN CD.DOC_STATUS = 21 THEN 'Invoice(A/R)'
        ELSE CAST(CD.DOC_STATUS AS VARCHAR(10))
    END AS Status,
    SH.USER_DOC AS [S.O.No],
    CD.SMAN1_CODE AS [Sls],
    CD.DOC_DATE AS [Doc Date],
    CD.INV_DUE AS [Due Date],
    CD.DOC_TOTAL AS [Invoice Total],
    AA.OA AS [Open Amount],
    AA.B_00_30 AS [== 00 - 30 ==],
    AA.B_31_60 AS [== 31 - 60 ==],
    AA.B_61_90 AS [== 61 - 90 ==],
    AA.B_91_180 AS [== 91 - 180 ==],
    AA.B_181_360 AS [== 181 - 360 ==],
    AA.B_OVER_360 AS [== OVER 360 ==],
    CD.POST_GL_DATE AS [Apply to Period],
    CASE WHEN (CD.[NAME] NOT LIKE '%TOPCAST%' AND CD.[NAME] NOT LIKE '%SHANGHAI AML%' AND CD.[NAME] NOT LIKE '%SHENZHEN WESTLINK%') THEN 0 ELSE 1 END AS [Is_Intercom],
    CASE WHEN INS.USER_DOC IS NULL THEN 0 ELSE 1 END AS [Is_Not_Shipped],
    LTRIM(RTRIM(VI.CUST_PO)) 'CUSTOMER PO'
FROM AllInvoices CD
    LEFT JOIN INV_HDR IH ON CD.USER_DOC = IH.USER_DOC
    LEFT JOIN AllAging AA ON CD.USER_DOC = AA.USER_DOC_trim AND CD.LINE = AA.LINE
    LEFT JOIN TKT_HDR TH ON CD.PARENT_DOCCATEGORY = 'TK' AND CD.PARENT_DOC_NO = TH.DOC_NO
    LEFT JOIN SO_HDR SH ON TH.PARENT_DOC_NO = SH.DOC_NO AND TH.PARENT_DOCCATEGORY = 'SO'
    LEFT JOIN CUSTSEARCH CTS ON CD.ACCTNO = CTS.ACCTNO AND CD.SUBC = CTS.SUBC AND CUST_VEND IN ('C', 'B')
    LEFT JOIN #Inv_not_shipped INS ON CD.USER_DOC_trim = INS.USER_DOC
    LEFT JOIN VIEW_INV_SO VI ON VI.DOC_NO=IH.DOC_NO
WHERE (IH.DOC_STATUS <> 11 OR IH.DOC_STATUS IS NULL)
    AND ((CD.DOC_TOTAL > 0 AND FLOOR(AA.OA) >= 1)
    OR (CD.DOC_TOTAL < 0 AND FLOOR(AA.OA) <= -1))
    AND (CASE WHEN (CD.[NAME] NOT LIKE '%TOPCAST%' AND CD.[NAME] NOT LIKE '%SHANGHAI AML%' AND CD.[NAME] NOT LIKE '%SHENZHEN WESTLINK%') THEN 0 ELSE 1 END) = 0
    AND (CASE WHEN INS.USER_DOC IS NULL THEN 0 ELSE 1 END) = 0
ORDER BY CD.[NAME], CD.DOC_DATE
;
GO