-- ============================================================
-- Final Simplified Overdue Invoices Query
-- ============================================================

DECLARE @ASOFDAY DATETIME = GETDATE();

WITH PaymentAgg AS
(
    SELECT
        PAY_DOC_NO,
        PAY_DOC_CATEGORY,
        DOC_STATUS AS P_DOC_STATUS,
        SUM(CASE WHEN DOC_STATUS <> 11 THEN ISNULL(AMOUNT, 0) ELSE 0 END) AS TotalAmount,
        SUM(CASE WHEN DOC_STATUS = 11 THEN ISNULL(ORIG_NETAMOUNT, 0) ELSE 0 END) AS TotalVoidAmount,
        SUM(CASE WHEN DOC_STATUS <> 11 THEN ISNULL(C_AMOUNT, 0) ELSE 0 END) AS TotalCAmount,
        SUM(CASE WHEN DOC_STATUS = 11 THEN ISNULL(C_ORIG_NETAMOUNT, 0) ELSE 0 END) AS TotalCVoidAmount
    FROM VIEW_CUSTOMER_PAYMENT
    WHERE PERIOD_DATE <= @ASOFDAY AND PERIOD_DATE IS NOT NULL
    GROUP BY PAY_DOC_NO, PAY_DOC_CATEGORY, DOC_STATUS
),

InvoiceBalances AS
(
    SELECT
        V.*,
        LTRIM(RTRIM(V.USER_DOC)) AS USER_DOC_trim,
        ISNULL(V.DOC_TOTAL, 0) - (ISNULL(PA.TotalAmount, 0) + ISNULL(PA.TotalVoidAmount, 0)) AS OPEN_BALANCE,
        ISNULL(V.C_DOC_TOTAL, 0) - (ISNULL(PA.TotalCAmount, 0) + ISNULL(PA.TotalCVoidAmount, 0)) AS C_OPEN_BALANCE
    FROM VIEW_CUSTOMER_INV_AS_OF V
        LEFT JOIN PaymentAgg PA
            ON LTRIM(RTRIM(V.DOC_NO)) = LTRIM(RTRIM(PA.PAY_DOC_NO))
           AND V.DOC_CATEGORY = PA.PAY_DOC_CATEGORY
           AND V.DOC_STATUS = PA.P_DOC_STATUS
    WHERE V.COMPANYNO <> 3
    AND V.COMPANYNO <> 7
),

FilteredInvoices AS
(
    SELECT *
    FROM InvoiceBalances
    WHERE (
            (ARAP_CURENCY_STATE = 0 AND OPEN_BALANCE > 0)
            OR (ARAP_CURENCY_STATE = 1 AND C_OPEN_BALANCE > 0)
        )
        AND (DOC_STATUS <> 11 OR (DOC_STATUS = 11 AND UPDATED_DTE > @ASOFDAY))
        -- AND DOC_STATUS <> 11 
        AND INV_DATE <= @ASOFDAY
),

InvoicePayments AS
(
    SELECT
        FI.USER_DOC_trim,
        SUM(CL.AMOUNT) AS TotalPaid,
        SUM(CL.C_AMOUNT) AS C_TotalPaid
    FROM FilteredInvoices FI
        LEFT JOIN INV_HDR IH ON FI.USER_DOC = IH.USER_DOC
        LEFT JOIN CHECK_LINE CL 
            ON CL.PAY_DOC_CATEGORY = 'IV'
           AND CL.PAY_DOC_NO = IH.DOC_NO
           AND CL.DOC_TYPE = 'AR'
    WHERE CL.PAY_APPLY <= @ASOFDAY
    GROUP BY FI.USER_DOC_trim
)


-- Final Output
SELECT
    FI.COMPANYNO              AS [Company No.],
    FI.USER_DOC_trim          AS [Invoice No.],
    FI.[NAME]                 AS [Customer Name],
    FI.CURENCY_CONV           AS [Converted Currency],
    FI.DOC_DATE               AS [Document Date],
    FI.INV_DUE                AS [Due Date],
    ROUND(FI.DOC_TOTAL, 2)              AS [Invoice Total],
    ROUND(FI.C_DOC_TOTAL, 2)            AS [Converted Invoice Total],
    ROUND(FI.OPEN_BALANCE, 2)           AS [Open Balance],
    ROUND(FI.C_OPEN_BALANCE, 2)         AS [Converted Open Balance],
    ROUND(FI.DOC_TOTAL - ISNULL(IP.TotalPaid, 0), 2) AS [OA],
    ROUND(FI.C_DOC_TOTAL - ISNULL(IP.C_TotalPaid, 0), 2) AS [C_OA],
    FI.POST_GL_DATE           AS [Apply to Period],
    VI.CUST_PO                AS [Customer PO]
FROM FilteredInvoices FI
    LEFT JOIN InvoicePayments IP 
        ON FI.USER_DOC_trim = IP.USER_DOC_trim
    LEFT JOIN INV_HDR IH 
        ON FI.USER_DOC = IH.USER_DOC
    LEFT JOIN (
        SELECT 
            DOC_NO,
            MAX(LTRIM(RTRIM(CUST_PO))) AS CUST_PO
        FROM VIEW_INV_SO
        GROUP BY DOC_NO
    ) VI ON VI.DOC_NO = IH.DOC_NO
WHERE
    FI.USER_DOC_trim IN ('173013', '255257', '800001063', '800001272')
    -- ROUND(FI.C_DOC_TOTAL - ISNULL(IP.C_TotalPaid, 0), 2) >= 1
    -- AND CAST(FI.INV_DUE AS DATE) < CAST(@ASOFDAY AS DATE)
    -- AND (FI.[NAME] NOT LIKE '%TOPCAST%' 
    --      AND FI.[NAME] NOT LIKE '%SHANGHAI AML%' 
    --      AND FI.[NAME] NOT LIKE '%SHENZHEN WESTLINK%')
    -- AND FI.DOC_NO NOT IN (
    --     SELECT DISTINCT DOC_NO
    --     FROM VIEW_CUSTOMER_INV_AS_OF
    --     WHERE DOC_STATUS = 11
    -- )
ORDER BY FI.[NAME], FI.INV_DUE;