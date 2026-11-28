import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity, ArrowDownRight, ArrowUpRight, BadgeJapaneseYen, Bell, Building2, CalendarDays,
  Check, ChevronDown, ChevronRight, ChevronUp, CircleAlert, ClipboardList, Clock3, FileText, Filter,
  Home, Languages, LogOut, Menu, Plus, Search, Settings, ShieldCheck,
  Users, WalletCards, X,
} from "lucide-react";
import "./style.css";
import CollaborationWorkspace from "./collaboration.jsx";
import RentalPage, { rentalPages } from "./rental.jsx";
import { todayJst } from "./jst-date.js";

const COPY = {
  ja: {
    summaryOriginal: "原文",
    resetPanelTitle: "パスワード再設定",
    stage_inquiry: "反響",
    negotiationVisit: "訪問予定",
    negotiationDiscussion: "商談中",
    negotiationEstimate: "見積提示",
    resetRequestFailed: "リセットを申請できませんでした。",
    noAccounts: "アカウントがありません。",
    previousPeriod: "前期間",
    funnelReference: "参考値・世帯数",
    cohortReference: "正式 Cohort 転換率・同一世帯追跡",
    inquiryToReservation: "反響→予約",
    reservationToIntroduction: "予約→紹介",
    introductionToContract: "紹介→契約",
    customerDispute: "既存顧客の争議中",
    customerDisputeAction: "既存顧客・争議",
    entitlementFrozen: "報酬帰属の争議中",
    consentRevokedAt: "取消",
    disclosedAt: "共有",
    touchHistory: "接点履歴",
    greetingSuffix: "さん",
    trendLoadFailed: "業務トレンドを取得できませんでした。",
    trendLoading: "業務トレンドを読み込み中…",
    trendInvalid: "業務トレンドのデータを表示できません。",
    trendEmpty: "期間内に記録がありません",
    trendZero: "対象期間の合計は 0 です",
    trendRecentDays: (days) => `直近${days}日`,
    managementLoadFailed: "経営・管理データを取得できませんでした。",
    loadingRecords: "記録を読み込み中…",
    currentStageDistribution: "現在の段階分布",
    stage_terminal: "完了・見送り",
    clearSearch: "検索をクリア",
    searchLoading: "顧客を検索しています…",
    searchRetry: "再試行", searchNoResults: "該当する顧客が見つかりませんでした。",
    searchNoResultsHint: "検索キーワードをご確認ください。",
    searchViewAll: (count) => `すべての顧客を表示 (${count}件)`,
    introFilterDisputedName: "帰属争議", introFilterDisputedDescription: "帰属に関する確認が必要な世帯を表示しています。",
    introFilterUnassignedName: "担当未割当", introFilterUnassignedDescription: "担当者が未割当の世帯を表示しています。",
    introFilterValidityName: "紹介有効期間", introFilterValidityDescription: "紹介有効期間の確認が必要な世帯を表示しています。",
    introFilterGenericName: "業務条件", introFilterGenericDescription: "業務条件で絞り込み中です。",
    introSelectHousehold: "世帯を選択してください", introNoIntroductions: "紹介はまだありません",
    searchTruncated: "検索結果が多いため、一部のみ表示しています。条件を絞り込んでください。",
    searchCount: (count, truncated) => truncated ? `${count}件を表示中` : `${count}件の顧客が見つかりました`,
    product: "SumaiBoard", subtitle: "住宅相談ビジネス・業務基盤", today: "今日の業務",
    households: "顧客・世帯", introductions: "紹介・商談", revenue: "着工・報酬",
    management: "経営・管理", settings: "設定", search: "顧客・会社を検索…",
    todayTitle: "おはようございます、", todaySub: "今日の業務状況を確認しましょう。",
    appointments: "今日の予約", followups: "今日のフォロー", overdue: "超過タスク",
    activities: "本日の活動", household: "世帯", open: "開く", quickActivity: "活動を記録",
    dailyReport: "日報ドラフト", autoSummary: "自動サマリー", note: "今日のメモ",
    save: "保存する", pipeline: "紹介パイプライン", recentHouseholds: "担当世帯",
    viewAll: "すべて見る", stage: "現在ステージ", nextAction: "次のアクション",
    due: "期限", partner: "住宅会社", status: "ステータス", elapsed: "経過",
    contract: "契約", actualStart: "実際着工", confirmStart: "着工確認",
    confirmationEvidence: "確認証跡・メモ", confirm: "着工を確認して報酬を確定",
    entitlement: "報酬権利", basis: "計算根拠", amount: "報酬額", rule: "適用ルール",
    invoice: "請求へ", paid: "入金済みにする", disputed: "争議中", frozen: "請求対象外・金額凍結",
    partnerCreate: "紹介を追加", partnerSelect: "住宅会社", staffSelect: "担当者",
    add: "追加する", introduced: "紹介済", received: "受付確認済", negotiating: "商談中",
    scheduled: "訪問予定", visited: "訪問済", quoted: "見積提示", declined: "見送り",
    stages: "ステージ", firstTouch: "初回流入", latestTouch: "最新流入",
    consent: "同意・情報共有", audit: "監査ログ", controls: "管理・統制",
    stores: "店舗", funnel: "店舗別ファネル", monthly: "月別着工数・報酬",
    acquisitionFunnel: "相談から着工確認までのファネル", conversionRate: "前段階からの転換率",
    last90Days: "直近90日・StageEvent件数",
    exceptionCards: "業務例外・要対応", exception_overdue_followups: "期限超過フォロー",
    exception_partner_feedback: "住宅会社フィードバック超過",
    exception_unassigned_households: "担当者未割当の世帯",
    exception_unassigned_introductions: "担当者未割当の紹介",
    exception_construction_confirmation: "着工確認期限超過",
    exception_open_disputes: "未解決の紹介争議", exception_invoice_unpaid: "請求済・未入金",
    exceptionOpenRecord: "対象を開く",
    specialReports: "業務レポート・印刷", reportOperations: "店舗運営状況",
    reportFunnel: "相談・着工ファネル", reportAttribution: "流入経路",
    reportPartnerQuality: "住宅会社別報酬処理品質", openPdfReport: "PDFを開く",
    reportFailed: "PDFレポートを作成できませんでした。",
    stage_new_reservation: "新規予約", stage_first_consult: "初回相談済",
    stage_fp_diagnosis: "FP診断済", stage_introduction: "紹介済",
    stage_negotiation: "訪問・商談中", stage_contract: "契約", stage_construction: "着工",
    roi: "集客チャネルROI", risk: "争議・既存顧客", ruleVersions: "報酬ルール履歴",
    demoWarning: "デモデータ（仮データ）は全て架空です。", prototype: "非公式プロトタイプ",
    roleAdvisor: "顧問", roleManager: "店長", roleFinance: "本社・経理",
    roleExecutive: "社長", taskQueues: "優先対応", overdueLabel: "期限超過",
    counter_today_followups: "今日フォロー", counter_overdue: "期限超過",
    counter_appointments: "本日来店", counter_unassigned: "担当未割当",
    counter_fee_approval: "報酬承認待ち", counter_invoice_generation: "請求データ生成待ち",
    counter_invoice_unpaid: "請求済・未入金", counter_critical_risk: "重大業務リスク",
    counter_disputes: "紹介帰属争議", counter_construction_queue: "着工確認滞留",
    priorityHigh: "高", daysOverdue: "日超過", noPendingTasks: "未処理の業務はありません。",
    unitItems: "件", reminder_introduction_validity: "紹介有効期間",
    reminder_construction_evidence: "着工証拠提出期限", reminder_dispute_resolution: "争議処理期限",
    reminder_agreement_renewal: "提携契約更新期限", reminder_fee_rule_validity: "FeeRule適用期限",
    managerTitle: "今日の店舗運営", executiveTitle: "全社経営ダッシュボード", managerSub: "本店の業務状況を確認しましょう。", executiveSub: "全社の業務状況を確認しましょう。", trendEntry: "業務トレンドを見る", selectMetric: "指標", period: "期間",
    followupRate: "フォロー実行率", completeness: "データ完全性",
    nextActionRate: "次回アクション設定率", reportRate: "日報提出率",
    responseQuality: "顧客対応品質", sampleSize: "対象数", noScore: "総合点・ランキングは表示しません",
    reminders: "期限リマインダー", storeCompare: "同条件の店舗比較", cohort: "相談月別コホート",
    selectedDeadline: "選択した期限対象", deadlineRecord: "対象レコード",
    partnerQuality: "住宅会社別・報酬処理品質", attribution: "流入経路分析",
    dashboardPrefs: "ホーム画面の表示設定", notificationPrefs: "通知設定",
    inApp: "アプリ内通知", emailNotice: "メール通知", savePreferences: "設定を保存",
    accountingNote: "本番では会計システムから請求・入金状態を受信します。SumaiBoard は請求書発行・入金消込を行いません。",
    plannedFee: "着工予定報酬", feeReview: "報酬条件確認中", approvedFee: "報酬承認済額",
    invoiceAmount: "請求額", paidAmount: "入金額", confirmedRevenue: "確定売上",
    referenceAmount: "争議中参考金額", frozenAmount: "凍結金額", approve: "承認",
    construction_planned_due: "予定日到来・未確認", construction_planned_due_today: "本日予定・未確認",
    construction_evidence_missing: "証拠未提出", construction_pending_review: "着工済・未審査",
    construction_delayed: "延期", operationsStatus: "店舗運営状況",
    dateLabel: "日付", userLabel: "ユーザー", actionLabel: "操作", targetLabel: "対象", detailLabel: "詳細",
    disputeType_referral: "紹介帰属争議", disputeType_amount: "報酬金額争議",
    disputeType_construction: "着工証拠争議", decisionReason: "裁定理由",
    reassessment: "再調査", writeOff: "報酬を償却", resolveDispute: "争議を裁定",
    stateConfirmed: "確認済", stateInvoiced: "請求データ生成済", statePaid: "入金済",
    stateDisputed: "争議中", statePendingConfirmation: "確認待ち", stateEstimated: "見積",
    statePotential: "見込", stateWrittenOff: "償却", statePending: "承認待ち",
    filterStore: "店舗", filterStage: "ステージを絞り込む", allStores: "全店舗",
    statusActive: "相談中", statusCompleted: "完了", statusLost: "見送り",
    managementSub: "店舗・流入・着工・報酬を同じ事実データから可視化", months: "か月",
    caseVolume: "案件数帯",
    slaPending: "SLA日数はデモ用の暫定値です。正式値は会社確認後に設定してください。",
    role: "デモロール", language: "言語", reset: "デモデータをリセット",
    resetConfirm: "デモデータを初期状態に戻します。よろしいですか？",
    resetDone: "デモデータを初期状態に戻しました。",
    businessTasksOverdueName: "期限超過タスク", businessTasksOverdueDescription: "本人の未完了タスクのうち、期限を過ぎているタスクがある世帯を表示しています。",
    businessTasksTodayName: "今日の対応タスク", businessTasksTodayDescription: "期限が本日以前の未完了タスクがある世帯を表示しています。",
    businessTasksCriticalName: "重要・期限超過タスク", businessTasksCriticalDescription: "優先度が高く、期限を過ぎているタスクがある世帯を表示しています。",
    businessTasksPartnerName: "パートナー回答待ちタスク", businessTasksPartnerDescription: "パートナーからの回答待ちで、期限を過ぎているタスクがある世帯を表示しています。",
    businessAppointmentsName: "本日の予定タスク", businessAppointmentsDescription: "本日に予定されている来店・面談タスクがある世帯を表示しています。",
    businessUnassignedName: "担当未割当", businessUnassignedDescription: "担当者が割り当てられていない世帯を表示しています。",
    businessValidityName: "紹介有効期間が接近", businessValidityDescription: "紹介の有効期間が30日以内に迫っている世帯を表示しています。",
    businessDisputedName: "帰属争議あり", businessDisputedDescription: "帰属争議中の紹介がある世帯を表示しています。",
    businessGenericName: "業務条件", businessGenericDescription: "業務条件で絞り込み中です。",
    revFilterUnit: "件",
    revFilterConstructionPendingName: "着工確認滞留",
    revFilterConstructionPendingDesc: "着工確認が未完了のプロジェクトを表示しています。",
    revFilterConstructionName: "着工確認",
    revFilterConstructionDesc: "着工確認キューを状態で絞り込んでいます。",
    revFilterEntPendingName: "報酬承認待ち",
    revFilterEntPendingDesc: "承認待ちの報酬レコードを表示しています。",
    revFilterEntInvoicedName: "請求済・未入金",
    revFilterEntInvoicedDesc: "請求済みで未入金の報酬レコードを表示しています。",
    revFilterEntInvoiceDataPendingName: "請求データ生成待ち",
    revFilterEntInvoiceDataPendingDesc: "請求データが未生成の確定報酬レコードを表示しています。",
    revFilterDisputedName: "帰属争議",
    revFilterDisputedDesc: "争議中の報酬レコードを表示しています。",
    revFilterAreaQueue: "着工確認キュー",
    revFilterAreaLedger: "報酬台帳",
    revMetricsNote: "全体集計（現在の一覧フィルターとは独立）",
    revNoMatchingProjects: "条件に一致するプロジェクトはありません",
    revNoMatchingRecords: "条件に一致するレコードはありません",
    revNoDisputes: "争議中のレコードはありません",
    clearBusinessFilter: "条件を解除", businessTerminalExcludedNote: "完了・見送りの世帯に紐づくタスク {count} 件は対象外です。", targetHouseholds: "対象世帯", targetTasks: "対象タスク",
    nextActionUnset: "未設定", noMatchingTasks: "対象タスクはありません", noMatchingHouseholds: "条件に一致する世帯はありません", noHouseholds: "世帯がありません", viewHousehold: "世帯詳細を見る →",
    noRows: "表示するデータがありません。",
    first: "初回", last: "最新", person: "ご家族", budget: "ご予算", area: "希望エリア",
    land: "土地", history: "ステージ履歴", activitiesHistory: "活動履歴",
    introduction: "紹介先", negotiations: "並行商談", people: "担当者", show: "詳細",
    close: "閉じる", addActivity: "活動を登録", activityType: "活動種別", body: "内容",
    nextDue: "次回期限", send: "登録", cancel: "キャンセル", meeting: "面談", phone: "電話",
    line: "LINE", visit: "訪問同行", memo: "メモ", success: "操作が完了しました。",
    error: "操作に失敗しました。", find: "検索", all: "すべて", choose: "選択してください",
    stageNow: "ステージを更新", selectStage: "ステージ", record: "更新する",
    startPlanned: "着工予定", confirmed: "着工確認済", evidence: "証跡",
    review: "詳細を確認", days: "日", noEntitlement: "着工確認後に報酬権利が生成されます。",
    amountRule: "請負金額 × 料率", currentRole: "表示ロール", loggingOut: "ログアウト",
    systemConfig: "運用設定", changeReason: "変更理由（10〜500文字）", saveConfig: "設定を保存",
    configSaved: "設定を保存しました。", configLoadError: "設定を読み込めません。",
    configPermission: "運用設定の変更は本社・経理ロールに限定されています。",
    actionQueue: "対応待ち", actionRequired: "対応が必要", businessTrend: "業務トレンド",
    dailySummary: "日報サマリー", businessOverview: "業務概況", businessIntelligence: "経営分析",
    storeComparison: "店舗比較", storeOperations: "店舗運営", deadlineReminders: "期限リマインダー",
    marketingAttribution: "マーケティング流入分析", cohortConversion: "相談月別転換",
    partnerSettlementQuality: "住宅会社別報酬処理品質", governance: "ガバナンス",
    versionedOperations: "バージョン管理された運用設定", personalWorkspace: "個人ワークスペース",
    touch: "接点", customerRelationship: "顧客関係", partnerJourney: "住宅会社との紹介",
    constructionRevenue: "着工・報酬", constructionConfirmation: "着工確認", revenueLedger: "報酬台帳",
    projectMilestone: "工事マイルストーン", systemPreferences: "システム設定",
    household360: "世帯360°", activityLog: "活動記録", partnerIntroduction: "住宅会社紹介",
    appendOnlyAudit: "追記専用監査", l1Protected: "L1 保護",
    referralLetters: "紹介状PDF", generateReferralLetter: "紹介状を作成",
    referralConsentRequired: "住宅会社別の有効な紹介状作成同意が必要です。",
    referralDocumentFailed: "紹介状を作成できませんでした。条件を確認して再試行してください。",
    referralNoDocuments: "紹介状はまだありません。", referralPreview: "プレビュー",
    referralDownload: "ダウンロード", referralExpires: "有効期限",
    referralExpired: "期限切れ", referralUnavailable: "ファイル利用不可",
    searchError: "検索を完了できませんでした。",
    recordReferralConsent: "紹介状作成の同意を記録", referralConsentActive: "同意有効",
    referralConsentRevoked: "同意取消済", referralConsentMethod: "同意方法",
    consentEvidenceReference: "同意証跡の参照番号", consentConfirmed: "本人の同意を確認しました",
    signedForm: "署名済み書面", webForm: "Webフォーム", recordedCall: "記録済み通話",
    revokeReferralConsent: "同意を取り消す", revokeReason: "取消理由",
    settingsSub: "デモ環境の表示とデータを管理",
    householdsSub: "顧客情報・接点・商談状況を一元管理",
    introductionsSub: "一つの家庭に対する複数住宅会社との並行商談を追跡",
    revenueSub: "予定・実際・確認を分けて記録し、報酬の根拠と状態を追跡",
    roleDescription: "役割ごとに表示と操作権限が異なります。",
    languageDescription: "日本語を標準表示とし、中文へ切り替えられます。",
    consentDescription: "L1 原始診断データは初期状態で非表示です。共有履歴は対象世帯の詳細画面で確認できます。",
    resetDescription: "世帯・紹介・着工・報酬を含むデモデータを初期状態に戻します。",
    financeRoleOnly: "本社・経理ロールで実行できます。",
    workspace: "ワークスペース", demoEnvironment: "デモ環境",
    loginTitle: "SumaiBoard にログイン", loginSubtitle: "登録済みアカウントでサインインしてください。",
    demoLogin: "デモアカウントでワンクリックログイン", employeeCode: "社員番号", password: "パスワード",
    signIn: "ログイン", signOut: "ログアウト", account: "アカウント",
    accounts: "アカウント管理", accountStatus: "アカウント状態", lastLogin: "最終ログイン",
    requestReset: "再設定リンクを発行", resetLink: "一回限りの再設定トークン",
    activeAccount: "有効", cannotLoadAccounts: "アカウント一覧を読み込めません。",
    resetRequest: "本人確認後、再設定用リンクを発行します。", verificationMethod: "本人確認方法",
    inPerson: "対面", verifiedCall: "確認済み通話", identityChecked: "本人確認済み",
    passwordRequired: "パスワードを入力してください。",
    changePasswordTitle: "初回パスワードを変更してください", currentPassword: "現在のパスワード",
    newPassword: "新しいパスワード", confirmPassword: "新しいパスワード（確認）",
    passwordMismatch: "新しいパスワードが一致しません。", changePassword: "パスワードを変更",
    notifications: "通知", markRead: "既読にする", archiveNotification: "アーカイブ",
    noNotifications: "通知はありません。", unreadNotifications: "未読",
    notificationTASK: "タスク", notificationAPPROVAL: "承認", notificationEXPENSE: "経費",
    notificationDAILY_REPORT: "日報", notificationIMPORT: "取込", notificationMONTHLY_CLOSE: "月次締め",
    notificationDOCUMENT: "文書", notificationEXPORT: "出力", notificationDATA_CORRECTION: "データ修正",
    notificationSECURITY: "セキュリティ", notificationSYSTEM: "システム",
    emailFallbackNote: "メール送信は未連携です。有効にすると未配信分を対応タスクに登録します。",
    dataCorrection: "顧客データ修正", requestCorrection: "修正を申請",
    correctionField: "修正項目", correctionValue: "修正後の値", correctionReason: "修正理由",
    correctionPending: "修正承認待ち", correctionApprove: "修正を承認", correctionReject: "差し戻す",
    disclosure: "第三者提供記録", discloseTo: "提供先の住宅会社", disclosureScope: "提供範囲",
    recordDisclosure: "提供記録を登録", shareConsent: "有効な同意", noActiveConsent: "選択範囲の有効な同意がありません。",
    disclosureRecordOnly: "この操作は同意と提供の記録のみを作成します。データ送信は行いません。",
    correctionRepresentative: "代表者名", correctionArea: "希望エリア",
    correctionBudget: "予算帯", correctionLand: "土地状況",
    landYes: "有", landNo: "無", landConsidering: "検討中",
    dataOps: "運用・ガバナンス", opsRefresh: "状態を更新", opsDatabase: "データベース",
    opsOutbox: "監査 Outbox", opsDeadLetters: "デッドレター", opsExpiredExports: "期限切れ出力",
    opsSessionCount: "有効セッション", opsEmail: "メール連携", opsConfigured: "未設定・タスクへフォールバック",
    opsAuditChain: "監査チェーン", opsFallbackTasks: "通知フォールバックタスク",
    opsSeedBatch: "デモデータバッチ", opsOk: "正常", opsDegraded: "要確認",
    opsNotConfigured: "未設定", opsRefreshTime: "最終確認",
    expenses: "経費申請", expenseCategory: "経費区分", expenseAmount: "金額（円）",
    expenseDescription: "内容", expenseDate: "利用日", attachReceipt: "証憑（PDF・画像）",
    appliedAt: "申請日", consumptionTax: "消費税額", taxCategory: "税区分",
    recordedProof: "計上根拠", taxInclusive: "税込",
    createDraft: "下書きを作成", submitExpense: "承認申請", approveExpense: "承認",
    rejectExpense: "差し戻す", recordExpense: "経理記録", receipt: "証憑を開く",
    expenseStatusDRAFT: "下書き", expenseStatusSUBMITTED: "承認待ち",
    expenseStatusAPPROVED: "承認済み", expenseStatusREJECTED: "差し戻し",
    expenseStatusRECORDED: "経理記録済み", expenseReason: "差し戻し理由",
    dataExchange: "CSV / PDF 入出力", exportResource: "出力データ", exportFile: "ファイルを作成",
    exportFormat: "出力形式", formatCsv: "CSV", formatPdf: "PDFレポート",
    importKintone: "kintone CSVを取り込む", includePersonalData: "個人情報を含める（管理者のみ）",
    importFieldMapping: "CSV項目マッピング", importExternalId: "外部ID", importRepresentative: "代表者名",
    importStore: "店舗ID", importAdvisorCode: "担当顧問の社員番号", importBudget: "予算帯",
    importArea: "希望エリア", importUnmapped: "割り当てなし", runDryRun: "ドライラン",
    confirmImport: "確認して取り込む", previewReady: "取込可能", previewExpiry: "このプレビューは1時間有効です。",
    previewStale: "マッピングが変更されています。再度ドライランを実行してください。",
    previewRequired: "取り込み前にドライランを実行してください。",
    exportHouseholds: "顧客一覧", exportIntroductions: "紹介一覧", exportExpenses: "経費一覧",
    exportFees: "報酬一覧", exportInvoices: "会計連携データ一覧", importResults: "取り込み結果",
    importedRows: "取り込み済み", skippedRows: "スキップ", errorRows: "エラー",
    downloadCsv: "ダウンロード", kintoneCsv: "kintone CSVファイル", truncated: "先頭200行を表示しています。",
    importStatusIMPORTED: "取り込み済み", importStatusSKIPPED: "スキップ", importStatusERROR: "エラー",
    invoiceCsvNote: "CSV / PDF は会計連携データの一覧です。請求書の発行や入金消込は行いません。",
    monthClose: "月次締め", monthCloseDescription: "月次スナップショットはバージョン管理され、締め後の対象レコードはロックされます。",
    closePeriod: "対象月", prepareClose: "スナップショットを準備", closePeriodAction: "月次締めを確定",
    requestReopen: "再オープンを申請", approveReopen: "再オープンを承認",
    reopenReason: "再オープン理由（10〜1000文字）", snapshotHash: "スナップショット SHA-256",
    lockedRecords: "締めロック", monthCloseError: "月次締めの操作に失敗しました。再読み込みして確認してください。",
    monthCloseEmpty: "月次締め履歴がありません。", separateApproval: "準備者とは別の承認者が必要です。",
    accountingNotDeveloped: "本機能は月次集計・ロック管理です。請求書発行や入金消込は行いません。",
    snapshotDetails: "集計スナップショット", closePrepared: "準備済み", closeClosed: "締め済み",
    reopenRequested: "再オープン承認待ち", reopened: "再オープン済み", locked: "ロック中", unlocked: "ロックなし",
    workToday: "今日の仕事", deadlineReminder: "期限の確認", businessRegistration: "業務登録",
    workHistory: "業務記録", todayWorkCount: "本日対応する業務", overdueCount: "期限超過",
    recentActivity: "最近の処理記録", noRecentActivity: "最近の処理記録はありません。",
    pendingTask: "未対応", inProgressTask: "対応中", deadlineBreakdown: "期限超過: {overdue} · 3 日: {dueSoon} · 不可相加",
    openTodayWork: "今日の一覧を開く", openOverdue: "期限超過を確認", createActivity: "活動を記録",
    createExpense: "経費を申請", openWorkHistory: "日報・記録を確認", collaboration: "チーム業務",
    schedule: "全員の日程", bulletin: "掲示板", negotiationQueue: "商談キュー",
    backToWorkspace: "今日の仕事へ戻る", previousWeek: "前週", nextWeek: "翌週",
    calendarEmpty: "この期間に予定はありません。", newSchedule: "予定を登録",
    eventTitle: "予定名", eventType: "予定の種類", eventStart: "開始日時", eventEnd: "終了日時",
    eventVisibility: "公開範囲", privateEvent: "自分のみ", storeEvent: "店舗内", companyEvent: "全社",
    eventMeeting: "会議", eventTrip: "出張", eventPersonal: "個人予定",
    eventAppointment: "来店予約", eventTask: "タスク期限", saveSchedule: "予定を保存",
    updateSchedule: "予定を更新", cancelEdit: "編集をやめる", allDay: "終日",
    postTitle: "タイトル", postBody: "本文", postCategory: "分類", postVisibility: "公開範囲",
    reportDate: "日報の日付", pinPost: "掲示板の上部に固定",
    postDaily: "日報", postMeeting: "会議記録", postNotice: "お知らせ", postShared: "共有",
    publishPost: "投稿する", editPost: "編集", archivePost: "アーカイブ", comment: "コメント",
    addComment: "コメントを追加", noPosts: "投稿はありません。", searchPosts: "投稿を検索",
    bulletinAllMonths: "すべての月", bulletinClearMonth: "月をクリア", bulletinNoPosts: "掲示板の投稿はありません", bulletinNoMatchingPosts: "条件に一致する投稿はありません",
    calendarWeekEmpty: "この週の予定はありません", calendarNoEmployees: "表示できる従業員がいません",
    auditCatSystem: "システム記録", auditCatBusiness: "業務記録", auditCatAudit: "監査記録", auditDemoRoleSwitch: "デモアカウント切替",
    postMonth: "対象月", dailyReportPublish: "日報ドラフトを共有",
    queueAction: "次の行動", queueOwner: "担当者", queueStage: "商談段階",
    queueRisk: "リスク", riskNone: "通常", riskWatch: "要確認", riskHigh: "優先",
    saveQueueAction: "行動を保存", noNegotiations: "対応対象の商談はありません。",
    systemManagement: "\u30b7\u30b9\u30c6\u30e0\u7ba1\u7406", descHouseholds: "\u9867\u5ba2\u30fb\u4e16\u5e2f\u306e\u4e00\u89a7\u3001\u8a73\u7d30\u3001\u5c65\u6b74", descIntroductions: "\u7d39\u4ecb\u3068\u5546\u8ac7\u306e\u9032\u6357\u7ba1\u7406", descRevenue: "\u7740\u5de5\u78ba\u8a8d\u3068\u5831\u916c\u306e\u51e6\u7406\u72b6\u6cc1", descTeam: "\u5168\u54e1\u306e\u65e5\u7a0b\u3001\u63b2\u793a\u677f\u3001\u5546\u8ac7\u30ad\u30e5\u30fc", descManagement: "\u7d4c\u55b6\u6307\u6a19\u3068\u5e97\u8217\u904b\u55b6\u306e\u72b6\u6cc1", descSettings: "\u8868\u793a\u3001\u901a\u77e5\u3001\u696d\u52d9\u306e\u8a2d\u5b9a", descAccounts: "\u30a2\u30ab\u30a6\u30f3\u30c8\u3068\u6a29\u9650\u306e\u7ba1\u7406",
    copyright: "© 2026 SUZIRUI · V3.0.2",
  },
  zh: {
    summaryOriginal: "原文",
    resetPanelTitle: "密码重置",
    stage_inquiry: "咨询",
    negotiationVisit: "计划拜访",
    negotiationDiscussion: "洽谈中",
    negotiationEstimate: "已提供报价",
    resetRequestFailed: "无法提交密码重置请求。",
    noAccounts: "暂无账号。",
    previousPeriod: "上一期间",
    funnelReference: "参考值・家庭数",
    cohortReference: "正式 Cohort 转化率・同一家庭追踪",
    inquiryToReservation: "咨询→预约",
    reservationToIntroduction: "预约→介绍",
    introductionToContract: "介绍→签约",
    customerDispute: "既有客户争议中",
    customerDisputeAction: "既有客户争议",
    entitlementFrozen: "报酬归属争议中",
    consentRevokedAt: "撤回",
    disclosedAt: "共享",
    touchHistory: "接触记录",
    greetingSuffix: "",
    trendLoadFailed: "无法加载业务趋势。",
    trendLoading: "正在加载业务趋势…",
    trendInvalid: "无法显示业务趋势数据。",
    trendEmpty: "所选期间内暂无记录",
    trendZero: "所选期间合计为 0",
    trendRecentDays: (days) => `近${days}天`,
    managementLoadFailed: "无法加载经营管理数据。",
    loadingRecords: "正在加载记录…",
    currentStageDistribution: "当前阶段分布",
    stage_terminal: "完结・搁置",
    clearSearch: "清除搜索",
    searchLoading: "正在搜索客户…", searchRetry: "重试",
    searchNoResults: "没有找到匹配的顾客", searchNoResultsHint: "请确认顾客姓名、假名、顾客代码或电话号码。",
    searchViewAll: (count) => `查看全部 ${count} 位客户`,
    introFilterDisputedName: "归属争议", introFilterDisputedDescription: "当前显示归属关系需要确认的家庭。",
    introFilterUnassignedName: "未分配负责人", introFilterUnassignedDescription: "当前显示尚未分配负责人的家庭。",
    introFilterValidityName: "介绍有效期", introFilterValidityDescription: "当前显示需要确认介绍有效期的家庭。",
    introFilterGenericName: "业务条件", introFilterGenericDescription: "当前按业务条件筛选显示中。",
    introSelectHousehold: "请选择家庭", introNoIntroductions: "暂无介绍",
    searchTruncated: "搜索结果较多，仅显示部分结果。请缩小搜索条件。",
    searchCount: (count, truncated) => truncated ? `显示前 ${count} 位` : `找到 ${count} 位客户`,
    systemManagement: "\u7cfb\u7edf\u7ba1\u7406", descHouseholds: "\u987e\u5ba2\u3001\u5bb6\u5ead\u5217\u8868\u3001\u8be6\u60c5\u4e0e\u5386\u53f2", descIntroductions: "\u4ecb\u7ecd\u4e0e\u5546\u8c08\u8fdb\u5ea6\u7ba1\u7406", descRevenue: "\u5f00\u5de5\u786e\u8ba4\u4e0e\u62a5\u916c\u5904\u7406\u60c5\u51b5", descTeam: "\u5168\u5458\u65e5\u7a0b\u3001\u516c\u544a\u677f\u3001\u5546\u8c08\u961f\u5217", descManagement: "\u7ecf\u8425\u6307\u6807\u4e0e\u95e8\u5e97\u8fd0\u8425\u60c5\u51b5", descSettings: "\u663e\u793a\u3001\u901a\u77e5\u4e0e\u4e1a\u52a1\u8bbe\u7f6e", descAccounts: "\u8d26\u53f7\u4e0e\u6743\u9650\u7ba1\u7406",
    product: "SumaiBoard", subtitle: "住宅咨询业务管理平台", today: "今日工作",
    households: "客户家庭", introductions: "介绍与洽谈", revenue: "开工与报酬",
    management: "经营管理", settings: "设置", search: "搜索客户或公司…",
    todayTitle: "早上好，", todaySub: "查看今天的业务进展。",
    appointments: "今日预约", followups: "今日跟进", overdue: "超期任务",
    activities: "今日活动", household: "家庭", open: "打开", quickActivity: "记录活动",
    dailyReport: "日报草稿", autoSummary: "自动汇总", note: "今日备注",
    save: "保存", pipeline: "介绍管道", recentHouseholds: "负责家庭",
    viewAll: "查看全部", stage: "当前阶段", nextAction: "下一步", due: "截止日期",
    partner: "住宅公司", status: "状态", elapsed: "停留", contract: "签约",
    actualStart: "实际开工", confirmStart: "开工确认", confirmationEvidence: "确认依据/备注",
    confirm: "确认开工并生成报酬", entitlement: "报酬权利", basis: "计算依据", amount: "报酬金额",
    rule: "适用规则", invoice: "转为请款", paid: "标记已付款", disputed: "争议中",
    frozen: "不可请款 · 金额已冻结", partnerCreate: "新增介绍", partnerSelect: "住宅公司",
    staffSelect: "负责人", add: "添加", introduced: "已介绍", received: "已确认受理",
    negotiating: "洽谈中", scheduled: "预约访问", visited: "已访问", quoted: "已报价",
    declined: "未继续", stages: "业务阶段", firstTouch: "首次来源", latestTouch: "最近来源",
    consent: "授权与信息共享", audit: "审计日志", controls: "经营与管控", stores: "门店",
    funnel: "门店漏斗", monthly: "月度开工与报酬", roi: "获客渠道 ROI",
    acquisitionFunnel: "从咨询到开工确认的转化漏斗", conversionRate: "相较上一阶段的转化率",
    last90Days: "近90日・StageEvent数量",
    exceptionCards: "业务异常・待处理", exception_overdue_followups: "已超期跟进",
    exception_partner_feedback: "住宅公司反馈超期",
    exception_unassigned_households: "未分配负责人的家庭",
    exception_unassigned_introductions: "未分配负责人的介绍",
    exception_construction_confirmation: "开工确认超期",
    exception_open_disputes: "未解决的介绍争议", exception_invoice_unpaid: "已请款·未入金",
    exceptionOpenRecord: "打开对象",
    specialReports: "业务报告・打印", reportOperations: "门店运营情况",
    reportFunnel: "咨询・开工漏斗", reportAttribution: "来源渠道",
    reportPartnerQuality: "按住宅公司划分的报酬处理质量", openPdfReport: "打开 PDF",
    reportFailed: "无法生成 PDF 报告。",
    stage_new_reservation: "新预约", stage_first_consult: "首次咨询完成",
    stage_fp_diagnosis: "FP 诊断完成", stage_introduction: "已介绍",
    stage_negotiation: "访问・洽谈中", stage_contract: "已签约", stage_construction: "已开工",
    risk: "争议与既有客户", ruleVersions: "报酬规则版本", demoWarning: "演示数据（假数据）全部为虚构。",
    prototype: "非正式原型", roleAdvisor: "顾问", roleManager: "店长", roleFinance: "总部·财务",
    roleExecutive: "社长", taskQueues: "优先处理", overdueLabel: "超期",
    counter_today_followups: "今日跟进", counter_overdue: "超期",
    counter_appointments: "今日到店", counter_unassigned: "未分配负责人",
    counter_fee_approval: "待审批报酬", counter_invoice_generation: "待生成请款数据",
    counter_invoice_unpaid: "已请款·未入金", counter_critical_risk: "重大业务风险",
    counter_disputes: "介绍归属争议", counter_construction_queue: "开工确认滞留",
    priorityHigh: "高", daysOverdue: "天超期", noPendingTasks: "没有待处理事项。",
    unitItems: "项", reminder_introduction_validity: "介绍有效期",
    reminder_construction_evidence: "开工证据提交期限", reminder_dispute_resolution: "争议处理期限",
    reminder_agreement_renewal: "合作协议续约期限", reminder_fee_rule_validity: "FeeRule 适用期限",
    managerTitle: "今日门店运营", executiveTitle: "全社经营看板", managerSub: "查看本店今天的业务进展。", executiveSub: "查看全公司今天的业务进展。", trendEntry: "查看业务趋势", selectMetric: "指标", period: "期间",
    followupRate: "跟进执行率", completeness: "数据完整性",
    nextActionRate: "下次行动设置率", reportRate: "日报提交率",
    responseQuality: "客户响应质量", sampleSize: "样本数", noScore: "不显示总分或排名",
    reminders: "期限提醒", storeCompare: "同条件门店对比", cohort: "咨询月份群组",
    selectedDeadline: "已选提醒事项", deadlineRecord: "业务记录",
    partnerQuality: "按住宅公司查看报酬处理质量", attribution: "来源渠道分析",
    dashboardPrefs: "首页显示设置", notificationPrefs: "通知设置",
    inApp: "应用内通知", emailNotice: "邮件通知", savePreferences: "保存设置",
    accountingNote: "生产版由会计系统回传请款和入金状态。SumaiBoard 不开发票、不做入金核销。",
    plannedFee: "预计开工报酬", feeReview: "报酬条件确认中", approvedFee: "已审批报酬金额",
    invoiceAmount: "请款金额", paidAmount: "入金金额", confirmedRevenue: "已确认收入",
    referenceAmount: "争议参考金额", frozenAmount: "冻结金额", approve: "审批",
    construction_planned_due: "已到计划日·待确认", construction_planned_due_today: "计划今日·待确认",
    construction_evidence_missing: "未提交证据", construction_pending_review: "已开工·待审核",
    construction_delayed: "延期", operationsStatus: "门店运营情况",
    dateLabel: "日期", userLabel: "用户", actionLabel: "操作", targetLabel: "对象", detailLabel: "详情",
    disputeType_referral: "介绍归属争议", disputeType_amount: "报酬金额争议",
    disputeType_construction: "开工证据争议", decisionReason: "裁决理由",
    reassessment: "重新调查", writeOff: "核销报酬", resolveDispute: "处理争议",
    revFilterUnit: "件",
    revFilterConstructionPendingName: "开工确认滞留",
    revFilterConstructionPendingDesc: "当前显示尚未完成开工确认的项目。",
    revFilterConstructionName: "开工确认",
    revFilterConstructionDesc: "当前按状态筛选开工确认队列。",
    revFilterEntPendingName: "报酬待批准",
    revFilterEntPendingDesc: "当前显示待批准的报酬记录。",
    revFilterEntInvoicedName: "已开票未收款",
    revFilterEntInvoicedDesc: "当前显示已开票尚未收款的报酬记录。",
    revFilterEntInvoiceDataPendingName: "待生成开票数据",
    revFilterEntInvoiceDataPendingDesc: "当前显示尚未生成开票数据的已确定报酬记录。",
    revFilterDisputedName: "归属争议",
    revFilterDisputedDesc: "当前显示争议中的报酬记录。",
    revFilterAreaQueue: "开工确认队列",
    revFilterAreaLedger: "报酬台账",
    revMetricsNote: "整体汇总（与当前列表筛选相互独立）",
    revNoMatchingProjects: "没有符合条件的项目",
    revNoMatchingRecords: "没有符合条件的记录",
    revNoDisputes: "暂无争议中的记录",
    stateConfirmed: "已确认", stateInvoiced: "请款数据已生成", statePaid: "已入金",
    stateDisputed: "争议中", statePendingConfirmation: "待确认", stateEstimated: "预计",
    statePotential: "潜在", stateWrittenOff: "已核销", statePending: "待审批",
    filterStore: "门店", filterStage: "按阶段筛选", allStores: "全部门店",
    statusActive: "咨询中", statusCompleted: "已完成", statusLost: "已流失",
    managementSub: "基于同一事实数据查看门店、来源、开工与报酬", months: "个月",
    caseVolume: "案件量区间",
    slaPending: "SLA 天数为演示暂定值。正式数值待公司确认后配置。",
    role: "演示角色", language: "语言", reset: "重置演示数据",
    resetConfirm: "将演示数据恢复到初始状态，确定吗？", resetDone: "演示数据已恢复初始状态。",
    businessTasksOverdueName: "超期任务", businessTasksOverdueDescription: "显示本人未完成任务中存在已超期任务的家庭。",
    businessTasksTodayName: "今日处理任务", businessTasksTodayDescription: "显示存在截止日期为今天或更早的未完成任务的家庭。",
    businessTasksCriticalName: "重要・超期任务", businessTasksCriticalDescription: "显示存在优先级高且已超期任务的家庭。",
    businessTasksPartnerName: "等待合作方回复的任务", businessTasksPartnerDescription: "显示存在等待合作方回复且已超期任务的家庭。",
    businessAppointmentsName: "今日预约任务", businessAppointmentsDescription: "显示存在安排在今天的到店或面谈任务的家庭。",
    businessUnassignedName: "未分配负责人", businessUnassignedDescription: "显示尚未分配负责人的家庭。",
    businessValidityName: "介绍有效期临近", businessValidityDescription: "显示介绍有效期将在30天内到期的家庭。",
    businessDisputedName: "存在归属争议", businessDisputedDescription: "显示存在归属争议中介绍的家庭。",
    businessGenericName: "业务条件", businessGenericDescription: "正在按业务条件筛选。",
    clearBusinessFilter: "解除条件", businessTerminalExcludedNote: "关联到已完结/搁置家庭的任务 {count} 件不在显示范围内。", targetHouseholds: "目标家庭", targetTasks: "目标任务",
    nextActionUnset: "未设置", noMatchingTasks: "没有符合条件的任务", noMatchingHouseholds: "没有符合条件的家庭", noHouseholds: "没有家庭", viewHousehold: "查看家庭详情 →",
    noRows: "暂无数据。", first: "首次", last: "最近", person: "家庭成员", budget: "预算",
    area: "意向区域", land: "土地", history: "阶段记录", activitiesHistory: "活动记录",
    introduction: "介绍对象", negotiations: "并行洽谈", people: "负责人", show: "查看详情",
    close: "关闭", addActivity: "记录活动", activityType: "活动类型", body: "内容",
    nextDue: "下次跟进日期", send: "提交", cancel: "取消", meeting: "面谈", phone: "电话",
    line: "LINE", visit: "陪同访问", memo: "备注", success: "操作成功。",
    error: "操作失败。", find: "搜索", all: "全部", choose: "请选择",
    stageNow: "更新阶段", selectStage: "阶段", record: "更新",
    startPlanned: "计划开工", confirmed: "已确认开工", evidence: "凭据",
    review: "查看详情", days: "天", noEntitlement: "确认开工后将生成报酬权利。",
    amountRule: "合同金额 × 费率", currentRole: "当前角色", loggingOut: "退出登录",
    systemConfig: "系统运行设置", changeReason: "修改原因（10–500字）", saveConfig: "保存设置",
    configSaved: "设置已保存。", configLoadError: "无法加载设置。",
    configPermission: "系统运行设置仅限总部·财务角色修改。",
    actionQueue: "待处理队列", actionRequired: "需要处理", businessTrend: "业务趋势",
    dailySummary: "日报汇总", businessOverview: "业务概况", businessIntelligence: "经营分析",
    storeComparison: "门店对比", storeOperations: "门店运营", deadlineReminders: "期限提醒",
    marketingAttribution: "营销来源分析", cohortConversion: "咨询月份转化",
    partnerSettlementQuality: "住宅公司报酬处理质量", governance: "治理审计",
    versionedOperations: "版本化运营设置", personalWorkspace: "个人工作区",
    touch: "触点", customerRelationship: "客户关系", partnerJourney: "住宅公司介绍流程",
    constructionRevenue: "开工与报酬", constructionConfirmation: "开工确认", revenueLedger: "报酬台账",
    projectMilestone: "项目节点", systemPreferences: "系统设置",
    household360: "家庭360°", activityLog: "活动记录", partnerIntroduction: "住宅公司介绍",
    appendOnlyAudit: "仅追加审计记录", l1Protected: "L1 已保护",
    referralLetters: "介绍函 PDF", generateReferralLetter: "生成介绍函",
    referralConsentRequired: "需要有效的、针对该住宅公司的介绍函生成授权。",
    referralDocumentFailed: "无法生成介绍函，请检查条件后重试。",
    referralNoDocuments: "暂无介绍函。", referralPreview: "预览",
    referralDownload: "下载", referralExpires: "有效期至",
    referralExpired: "已过期", referralUnavailable: "文件不可用",
    searchError: "搜索失败，请稍后重试。",
    recordReferralConsent: "记录介绍函生成授权", referralConsentActive: "授权有效",
    referralConsentRevoked: "授权已撤销", referralConsentMethod: "授权方式",
    consentEvidenceReference: "授权凭证引用编号", consentConfirmed: "已确认本人授权",
    signedForm: "已签署书面文件", webForm: "Web 表单", recordedCall: "已记录通话",
    revokeReferralConsent: "撤销授权", revokeReason: "撤销原因",
    settingsSub: "管理演示环境的显示与数据",
    householdsSub: "统一管理客户信息、接点和洽谈状态",
    introductionsSub: "追踪同一家庭与多家住宅公司的并行洽谈",
    revenueSub: "分别记录计划、实际与确认日期，并追踪报酬依据和状态",
    roleDescription: "不同角色拥有不同的数据视图和操作权限。",
    languageDescription: "默认显示日语，并可切换为中文。",
    consentDescription: "L1 原始诊断数据默认隐藏。共享记录可在家庭详情中查看。",
    resetDescription: "将家庭、介绍、开工和报酬等演示数据恢复到初始状态。",
    financeRoleOnly: "请切换到总部·财务角色执行。",
    workspace: "工作区", demoEnvironment: "演示环境",
    loginTitle: "登录 SumaiBoard", loginSubtitle: "请使用已配置的账号登录。",
    demoLogin: "演示账号一键登录", employeeCode: "员工编号", password: "密码",
    signIn: "登录", signOut: "退出登录", account: "账号",
    accounts: "账号管理", accountStatus: "账号状态", lastLogin: "最近登录",
    requestReset: "生成重置链接", resetLink: "一次性重置令牌",
    activeAccount: "启用", cannotLoadAccounts: "无法加载账号列表。",
    resetRequest: "完成本人核验后生成密码重置链接。", verificationMethod: "身份核验方式",
    inPerson: "当面", verifiedCall: "已核验的视频通话", identityChecked: "已完成身份核验",
    passwordRequired: "请输入密码。",
    changePasswordTitle: "请修改初始密码", currentPassword: "当前密码",
    newPassword: "新密码", confirmPassword: "确认新密码",
    passwordMismatch: "两次输入的新密码不一致。", changePassword: "修改密码",
    notifications: "通知", markRead: "标记为已读", archiveNotification: "归档",
    noNotifications: "暂无通知。", unreadNotifications: "未读",
    notificationTASK: "任务", notificationAPPROVAL: "审批", notificationEXPENSE: "费用",
    notificationDAILY_REPORT: "日报", notificationIMPORT: "导入", notificationMONTHLY_CLOSE: "月度结账",
    notificationDOCUMENT: "文档", notificationEXPORT: "导出", notificationDATA_CORRECTION: "数据修正",
    notificationSECURITY: "安全", notificationSYSTEM: "系统",
    emailFallbackNote: "尚未接入邮件发送。启用后未发送的通知会转为待办任务。",
    dataCorrection: "客户数据修正", requestCorrection: "申请修正",
    correctionField: "修正字段", correctionValue: "修正后的值", correctionReason: "修正原因",
    correctionPending: "待审批修正", correctionApprove: "批准修正", correctionReject: "退回",
    disclosure: "第三方提供记录", discloseTo: "接收住宅公司", disclosureScope: "提供范围",
    recordDisclosure: "记录提供", shareConsent: "有效同意", noActiveConsent: "该范围没有有效同意。",
    disclosureRecordOnly: "此操作仅记录同意和提供事项，不会实际传输数据。",
    correctionRepresentative: "代表人姓名", correctionArea: "期望地区",
    correctionBudget: "预算范围", correctionLand: "土地情况",
    landYes: "有", landNo: "无", landConsidering: "考虑中",
    dataOps: "运维与治理", opsRefresh: "刷新状态", opsDatabase: "数据库",
    opsOutbox: "审计 Outbox", opsDeadLetters: "死信", opsExpiredExports: "过期导出",
    opsSessionCount: "有效会话", opsEmail: "邮件集成", opsConfigured: "未配置，改为待办任务",
    opsAuditChain: "审计链", opsFallbackTasks: "通知兜底任务",
    opsSeedBatch: "演示数据批次", opsOk: "正常", opsDegraded: "需检查",
    opsNotConfigured: "未配置", opsRefreshTime: "最近检查",
    expenses: "费用申请", expenseCategory: "费用类别", expenseAmount: "金额（日元）",
    expenseDescription: "内容", expenseDate: "发生日期", attachReceipt: "凭证（PDF/图片）",
    appliedAt: "申请日期", consumptionTax: "消费税额", taxCategory: "税区分",
    recordedProof: "记账依据", taxInclusive: "含税",
    createDraft: "创建草稿", submitExpense: "提交审批", approveExpense: "批准",
    rejectExpense: "退回", recordExpense: "财务记账", receipt: "查看凭证",
    expenseStatusDRAFT: "草稿", expenseStatusSUBMITTED: "待审批",
    expenseStatusAPPROVED: "已批准", expenseStatusREJECTED: "已退回",
    expenseStatusRECORDED: "已记账", expenseReason: "退回原因",
    dataExchange: "CSV / PDF 导入导出", exportResource: "导出数据", exportFile: "生成文件",
    exportFormat: "导出格式", formatCsv: "CSV", formatPdf: "PDF 报表",
    importKintone: "导入 kintone CSV", includePersonalData: "包含个人信息（仅管理员）",
    importFieldMapping: "CSV 字段映射", importExternalId: "外部 ID", importRepresentative: "代表者姓名",
    importStore: "门店 ID", importAdvisorCode: "负责顾问员工编号", importBudget: "预算范围",
    importArea: "意向区域", importUnmapped: "不映射", runDryRun: "运行预检",
    confirmImport: "确认并导入", previewReady: "可导入", previewExpiry: "此预检结果有效期为 1 小时。",
    previewStale: "字段映射已更改，请重新运行预检。",
    previewRequired: "导入前请先运行预检。",
    exportHouseholds: "客户列表", exportIntroductions: "介绍列表", exportExpenses: "费用列表",
    exportFees: "报酬列表", exportInvoices: "会计对接数据列表", importResults: "导入结果",
    importedRows: "已导入", skippedRows: "跳过", errorRows: "错误",
    downloadCsv: "下载", kintoneCsv: "kintone CSV 文件", truncated: "仅显示前 200 行。",
    importStatusIMPORTED: "已导入", importStatusSKIPPED: "跳过", importStatusERROR: "错误",
    invoiceCsvNote: "CSV / PDF 仅为会计对接数据列表，不会开具发票或进行收款核销。",
    monthClose: "月度结账", monthCloseDescription: "月度快照按版本保存，结账后锁定指定业务记录。",
    closePeriod: "目标月份", prepareClose: "准备快照", closePeriodAction: "确认月度结账",
    requestReopen: "申请重新开放", approveReopen: "批准重新开放",
    reopenReason: "重新开放原因（10–1000 字）", snapshotHash: "快照 SHA-256",
    lockedRecords: "结账锁定", monthCloseError: "月度结账操作失败，请刷新后重试。",
    monthCloseEmpty: "暂无月度结账记录。", separateApproval: "需要由准备人以外的人员审批。",
    accountingNotDeveloped: "本功能仅做月度汇总和锁定管理，不开具发票或核销收款。",
    snapshotDetails: "汇总快照", closePrepared: "已准备", closeClosed: "已结账",
    reopenRequested: "等待重新开放审批", reopened: "已重新开放", locked: "已锁定", unlocked: "未锁定",
    workToday: "今日工作", deadlineReminder: "查看期限", businessRegistration: "业务登记",
    workHistory: "工作记录", todayWorkCount: "今日需处理", overdueCount: "已超期",
    recentActivity: "最近处理记录", noRecentActivity: "暂无最近处理记录。",
    pendingTask: "待处理", inProgressTask: "进行中", deadlineBreakdown: "已超期: {overdue} · 3天内: {dueSoon} · 不可相加",
    openTodayWork: "查看今日清单", openOverdue: "查看超期事项", createActivity: "记录活动",
    createExpense: "申请费用", openWorkHistory: "查看日报与记录", collaboration: "团队协作",
    schedule: "全员日程", bulletin: "公告板", negotiationQueue: "洽谈队列",
    backToWorkspace: "返回今日工作", previousWeek: "上一周", nextWeek: "下一周",
    calendarEmpty: "此期间没有日程。", newSchedule: "新建日程",
    eventTitle: "日程名称", eventType: "日程类型", eventStart: "开始时间", eventEnd: "结束时间",
    eventVisibility: "可见范围", privateEvent: "仅自己", storeEvent: "门店内", companyEvent: "全公司",
    eventMeeting: "会议", eventTrip: "出差", eventPersonal: "个人安排",
    eventAppointment: "到店预约", eventTask: "任务期限", saveSchedule: "保存日程",
    updateSchedule: "更新日程", cancelEdit: "取消编辑", allDay: "全天",
    postTitle: "标题", postBody: "正文", postCategory: "分类", postVisibility: "可见范围",
    reportDate: "日报日期", pinPost: "置顶公告",
    postDaily: "日报", postMeeting: "会议记录", postNotice: "通知", postShared: "共享",
    publishPost: "发布", editPost: "编辑", archivePost: "归档", comment: "评论",
    addComment: "添加评论", noPosts: "暂无帖子。", searchPosts: "搜索帖子",
    bulletinAllMonths: "全部月份", bulletinClearMonth: "清除月份", bulletinNoPosts: "公告栏还没有帖子", bulletinNoMatchingPosts: "没有符合条件的帖子",
    calendarWeekEmpty: "本周暂无日程", calendarNoEmployees: "没有可显示的员工",
    auditCatSystem: "系统记录", auditCatBusiness: "业务记录", auditCatAudit: "审计记录", auditDemoRoleSwitch: "演示账号切换",
    postMonth: "月份", dailyReportPublish: "分享日报草稿",
    queueAction: "下一步行动", queueOwner: "负责人", queueStage: "洽谈阶段",
    queueRisk: "风险", riskNone: "正常", riskWatch: "需关注", riskHigh: "优先",
    saveQueueAction: "保存行动", noNegotiations: "暂无待处理洽谈。",
    copyright: "© 2026 SUZIRUI · V3.0.2",
  },
};

const CONFIG_LABELS = {
  ja: {
    "fee_rule.applicability_basis": "報酬ルール適用基準", "fee.bank_fee_tolerance_yen": "振込手数料許容額",
    "expense.approval_thresholds_yen": "経費承認しきい値", "expense.allowed_categories": "経費カテゴリ",
    "retention.interview_online_years": "面談データのオンライン保存年数",
    "retention.interview_archive_years": "面談データのアーカイブ年数",
    "retention.daily_report_years": "日報保存年数", "retention.monthly_report_years": "月報保存年数",
    "retention.month_close_snapshot_years": "月次締めスナップショット保存年数",
    "month_close.locked_resources": "月次締め後にロックする対象",
    "retention.audit_years": "監査記録保存年数", "attachment.allowed_extensions": "添付可能な拡張子",
    "attachment.max_file_mb": "添付ファイル上限（MB）", "import.max_csv_rows": "CSV取込上限行数",
    "construction.expected_start_months": "着工予定の標準月数",
    "search.alert_queries_per_minute": "検索アラートしきい値（回/分）",
    "notification.email_retry_minutes": "メール再試行間隔（分）",
    "notification.quiet_hours": "通知の静穏時間", "calendar.retry_minutes": "カレンダー同期再試行間隔（分）",
    "calendar.max_retries": "カレンダー同期の最大再試行数",
    "finance.sync_interval_minutes": "会計連携の同期間隔（分）",
    "finance.summary_stale_after_minutes": "会計サマリーの期限切れ判定（分）",
    "task.followup_sla_days": "フォロー期限（営業日）",
    "task.partner_feedback_sla_days": "住宅会社回答期限（日）",
    "task.construction_evidence_sla_days": "着工証拠提出期限（日）",
    "sla.introduction_validity_days": "紹介有効期間（仮設定・日）",
    "sla.construction_evidence_days": "着工証拠提出期間（仮設定・日）",
    "sla.dispute_resolution_days": "争議処理期間（仮設定・日）",
    "sla.agreement_renewal_days": "提携契約更新期間（仮設定・日）",
    "sla.fee_rule_validity_days": "FeeRule適用期限（仮設定・日）",
    "month_close.lock_working_day": "月次締めロック営業日",
    "expense.max_receipt_mb": "領収書ファイル上限（MB）",
    "export.max_csv_mb": "CSV出力サイズ上限（MB）", "export.max_pdf_mb": "PDF出力サイズ上限（MB）",
    "export.max_rows": "一覧出力の最大行数", "export.expiry_hours": "出力ファイル有効期間（時間）",
    "pdf.render_concurrency": "PDFレンダリング同時実行数",
    "pdf.render_max_pending": "PDFレンダリング待機上限", "pdf.render_timeout_seconds": "PDF生成タイムアウト（秒）",
    "pdf.referral_validity_days": "紹介状の有効期間（仮設定・日）",
  },
  zh: {
    "fee_rule.applicability_basis": "报酬规则适用依据", "fee.bank_fee_tolerance_yen": "转账手续费容差",
    "expense.approval_thresholds_yen": "费用审批阈值", "expense.allowed_categories": "费用类别",
    "retention.interview_online_years": "面谈数据在线保存年限",
    "retention.interview_archive_years": "面谈数据归档年限",
    "retention.daily_report_years": "日报保存年限", "retention.monthly_report_years": "月报保存年限",
    "retention.month_close_snapshot_years": "月结快照保存年限", "retention.audit_years": "审计记录保存年限",
    "month_close.locked_resources": "月度结账后锁定的对象",
    "attachment.allowed_extensions": "允许的附件扩展名", "attachment.max_file_mb": "附件大小上限（MB）",
    "import.max_csv_rows": "CSV 导入最大行数", "construction.expected_start_months": "预计开工标准月数",
    "search.alert_queries_per_minute": "搜索告警阈值（次/分）", "notification.email_retry_minutes": "邮件重试间隔（分）",
    "notification.quiet_hours": "通知静默时段", "calendar.retry_minutes": "日历同步重试间隔（分）",
    "calendar.max_retries": "日历同步最大重试次数", "finance.sync_interval_minutes": "会计同步间隔（分）",
    "finance.summary_stale_after_minutes": "会计摘要过期判定（分）", "task.followup_sla_days": "跟进期限（天）",
    "task.partner_feedback_sla_days": "住宅公司反馈期限（天）",
    "task.construction_evidence_sla_days": "开工证据提交期限（天）",
    "sla.introduction_validity_days": "介绍有效期（暂定·天）",
    "sla.construction_evidence_days": "开工证据提交期限（暂定·天）",
    "sla.dispute_resolution_days": "争议处理期限（暂定·天）",
    "sla.agreement_renewal_days": "合作协议续约期限（暂定·天）",
    "sla.fee_rule_validity_days": "FeeRule 适用期限（暂定·天）",
    "month_close.lock_working_day": "月结锁定工作日", "expense.max_receipt_mb": "收据文件大小上限（MB）",
    "export.max_csv_mb": "CSV 导出大小上限（MB）", "export.max_pdf_mb": "PDF 导出大小上限（MB）",
    "export.max_rows": "列表导出最大行数", "export.expiry_hours": "导出文件有效期（小时）",
    "pdf.render_concurrency": "PDF 渲染并发数",
    "pdf.render_max_pending": "PDF 渲染排队上限", "pdf.render_timeout_seconds": "PDF 生成超时（秒）",
    "pdf.referral_validity_days": "介绍函有效期（暂定·天）",
  },
};

const ROLE_LABEL = {
  ja: { advisor: "顧問", manager: "店長", hq_finance: "本社・財務", executive: "社長",
    store_manager: "店長", finance: "財務", administrator: "管理者", hq_staff: "本社担当", hr: "人事" },
  zh: { advisor: "顾问", manager: "店长", hq_finance: "总部·财务", executive: "社长",
    store_manager: "店长", finance: "财务", administrator: "管理员", hq_staff: "总部担当", hr: "人事" },
};
const ACCOUNT_STATUS = {
  PENDING_PROVISIONING: ["発行待ち", "待开通", "pending"],
  INVITED: ["招待済み", "已邀请", "pending"],
  ACTIVE: ["有効", "启用", "success"],
  TRANSFER_PENDING: ["異動待ち", "待调动", "pending"],
  LEAVE_RESTRICTED: ["休職・利用制限", "休假限制", "neutral"],
  SUSPENDED: ["停止中", "已暂停", "danger"],
  LOCKED_SECURITY: ["セキュリティロック", "安全锁定", "danger"],
  DEACTIVATED: ["無効", "已停用", "neutral"],
  ARCHIVED: ["保管済み", "已归档", "neutral"],
};

function roleLabel(locale, role) {
  if (role === "owner") return locale === "zh" ? "业主" : "オーナー";
  const labels = ROLE_LABEL[locale];
  return labels && Object.hasOwn(labels, role) ? labels[role] : role;
}

const jstDateTime = new Intl.DateTimeFormat("sv-SE", {
  timeZone: "Asia/Tokyo", year: "numeric", month: "2-digit", day: "2-digit",
  hour: "2-digit", minute: "2-digit", hourCycle: "h23",
});

function displayDate(value) {
  if (value == null || value === "") return "—";
  if (typeof value !== "string") return value;
  const match = /^(\d{4})-(\d{2})(?:-(\d{2})(?:[T ](\d{2}:\d{2})(?::\d{2}(?:\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?)?)?$/.exec(value);
  if (!match) return value;
  const [, year, month, day, time, zone] = match;
  if (zone) {
    const instant = new Date(value.replace(" ", "T"));
    if (Number.isNaN(instant.getTime())) return "—";
    const parts = Object.fromEntries(jstDateTime.formatToParts(instant).map(({ type, value }) => [type, value]));
    return `${parts.year}/${parts.month}/${parts.day} ${parts.hour}:${parts.minute}`;
  }
  return [year, month, day].filter(Boolean).join("/") + (time ? ` ${time}` : "");
}

function OriginalText({ value, sourceLocale, locale, t }) {
  const showMarker = locale === "zh" && sourceLocale === "ja" && Boolean(value?.trim());
  return <>
    {showMarker && <span className="summary-original">{t("summaryOriginal")}</span>}
    <span className="original-text" lang={sourceLocale}>{value}</span>
  </>;
}

function SummaryText({ summary, t, locale, className }) {
  // The daily report API exposes the Japanese-generated summary separately from the manual note.
  return <p className={className}>{summary?.trim()
    ? <OriginalText value={summary} sourceLocale="ja" t={t} locale={locale}/>
    : "—"}</p>;
}

function AccountStatus({ status, locale }) {
  const label = Object.hasOwn(ACCOUNT_STATUS, status) ? ACCOUNT_STATUS[status] : null;
  return <span className={"account-status " + (label?.[2] || "neutral")}>{label?.[locale === "zh" ? 1 : 0] || status || "—"}</span>;
}

function CustomerDisputeBadge({ t }) {
  return <span className="pill customer-dispute-badge">{t("customerDispute")}</span>;
}

const STAGES = ["新規予約", "初回相談済", "FP診断済", "紹介済", "訪問・商談中", "契約", "着工", "完了・見送り"];
const TERMINAL_STAGES = ["完了・見送り", "完了", "見送り"];
function matchBusinessTasks(businessFilter, tasks) {
  if (!(businessFilter.startsWith("tasks:") || businessFilter.startsWith("appointments:"))) return [];
  const taskFilter = businessFilter.split(":")[1];
  return tasks.filter((task) => {
    if (taskFilter === "overdue") return task.days_overdue > 0;
    if (taskFilter === "today_followups") return String(task.due_at).slice(0, 10) <= todayJst();
    if (taskFilter === "critical") return task.priority === "high" && task.days_overdue > 0;
    if (taskFilter === "partner_feedback") return task.task_type === "partner_feedback" && task.days_overdue > 0;
    return task.task_type === "appointment" && String(task.due_at).slice(0, 10) === todayJst();
  });
}
function isTaskBusinessFilter(value) { return value.startsWith("tasks:") || value.startsWith("appointments:"); }
function stageTagClass(stage) {
  const groups = { "stage-blue": ["新規予約", "初回相談済"], "stage-purple": ["FP診断済", "紹介済", "訪問・商談中"], "stage-amber": ["契約", "着工"], "stage-gray": ["完了・見送り"] };
  return `stage-tag ${Object.entries(groups).find(([, values]) => values.includes(stage))?.[0] || ""}`.trim();
}
function businessFilterKeys(value) {
  if (value === "tasks:overdue") return ["businessTasksOverdueName", "businessTasksOverdueDescription"];
  if (value === "tasks:today_followups") return ["businessTasksTodayName", "businessTasksTodayDescription"];
  if (value === "tasks:critical") return ["businessTasksCriticalName", "businessTasksCriticalDescription"];
  if (value === "tasks:partner_feedback") return ["businessTasksPartnerName", "businessTasksPartnerDescription"];
  if (value.startsWith("appointments:")) return ["businessAppointmentsName", "businessAppointmentsDescription"];
  if (value === "unassigned") return ["businessUnassignedName", "businessUnassignedDescription"];
  if (value === "validity:due") return ["businessValidityName", "businessValidityDescription"];
  if (value === "disputed") return ["businessDisputedName", "businessDisputedDescription"];
  return ["businessGenericName", "businessGenericDescription"];
}
const API_BASE = import.meta.env.VITE_API_BASE || "";

function App() {
  const [locale, setLocale] = useState(localStorage.getItem("sumaiboard-locale") || "ja");
  const [role, setRole] = useState("advisor");
  const [page, setPage] = useState("dashboard");
  const [workspaceView, setWorkspaceView] = useState("home");
  const [data, setData] = useState(null);
  const [authenticated, setAuthenticated] = useState(false);
  const [demoAccounts, setDemoAccounts] = useState([]);
  const [demoAvailable, setDemoAvailable] = useState(false);
  const [sampleMode, setSampleMode] = useState(false);
  const [loginError, setLoginError] = useState("");
  const [notifications, setNotifications] = useState([]);
  const [notificationUnreadCount, setNotificationUnreadCount] = useState(0);
  const [notificationCenterOpen, setNotificationCenterOpen] = useState(false);
  const notificationRequestId = useRef(0);
  const [tasks, setTasks] = useState([]);
  const [preferences, setPreferences] = useState({ dashboard_widgets: ["tasks", "overview"], notification_preferences: { in_app: true, email: false } });
  const [businessFilter, setBusinessFilter] = useState("");
  const [introFocusHouseholdId, setIntroFocusHouseholdId] = useState(null);
  const [selected, setSelected] = useState(null);
  const [modal, setModal] = useState("");
  const [query, setQuery] = useState("");
  const [searchMatches, setSearchMatches] = useState(null);
  const [searchResultIds, setSearchResultIds] = useState([]);
  const [searchTruncated, setSearchTruncated] = useState(false);
  const [searchStatus, setSearchStatus] = useState("idle");
  const [searchRetry, setSearchRetry] = useState(0);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchActiveIndex, setSearchActiveIndex] = useState(-1);
  const searchRequestId = useRef(0);
  const searchControlRef = useRef(null);
  const searchInputRef = useRef(null);
  const searchLaunchRef = useRef(null);
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const accountMenuRef = useRef(null);
  const [searchExpanded, setSearchExpanded] = useState(false);
  const [toast, setToast] = useState("");
  const [busy, setBusy] = useState(false);
  const t = (key) => COPY[locale][key] || key;

  async function refreshNotifications() {
    const requestId = ++notificationRequestId.current;
    const response = await fetch(`${API_BASE}/api/notifications`, { credentials: "include" });
    if (!response.ok) return;
    const result = await response.json();
    if (requestId !== notificationRequestId.current) return;
    setNotifications(result.items || []);
    setNotificationUnreadCount(result.unread_count || 0);
  }

  async function load() {
    const identityResponse = await fetch(`${API_BASE}/api/bootstrap`, { credentials: "include" });
    if (!identityResponse.ok) throw new Error("session expired");
    const identity = await identityResponse.json();
    setRole(identity.role);
    setSampleMode(Boolean(identity.environment?.public_sample));
    if (identity.user.must_change_password) {
      notificationRequestId.current += 1;
      setData(identity);
      setTasks([]);
      setNotifications([]);
      setNotificationUnreadCount(0);
      setPage("change-password");
      setAuthenticated(true);
      return identity;
    }
    const result = { ...identity, households: [] };
    if (["hr", "administrator"].includes(identity.account_role)) {
      const accountsResponse = await fetch(`${API_BASE}/api/accounts`, { credentials: "include" });
      if (!accountsResponse.ok) throw new Error("account access denied");
      Object.assign(result, await accountsResponse.json());
    }
    if (identity.account_role === "hr") setPage("accounts");
    else if (identity.account_role === "owner") setPage("owner-portal");
    else if (identity.environment?.public_sample) setPreferences(identity.preferences);
    else {
      const preferencesResponse = await fetch(`${API_BASE}/api/preferences`, { credentials: "include" });
      if (!preferencesResponse.ok) throw new Error("preferences access denied");
      setPreferences(await preferencesResponse.json());
    }
    setTasks([]);
    setData(result);
    setAuthenticated(true);
    if (selected) setSelected(result.households?.find((h) => h.id === selected.id) || null);
    await refreshNotifications();
    return result;
  }
  useEffect(() => {
    localStorage.setItem("sumaiboard-locale", locale);
    document.documentElement.lang = locale;
  }, [locale]);
  useLayoutEffect(() => {
    if (window.matchMedia("(max-width: 1023px)").matches) window.scrollTo(0, 0);
  }, [page, workspaceView]);
  useEffect(() => {
    fetch(`${API_BASE}/api/public-config`)
      .then(async (response) => (response.ok ? response.json() : null))
      .then((config) => { if (config?.public_sample) setSampleMode(true); })
      .catch(() => {});
  }, []);
  useEffect(() => {
    (async () => {
      try {
        await load();
      } catch {
        try {
          const configResponse = await fetch(`${API_BASE}/api/public-config`);
          const config = configResponse.ok ? await configResponse.json() : null;
          if (config?.public_sample) {
            const guestResponse = await fetch(`${API_BASE}/api/auth/guest-login`, {
              method: "POST", credentials: "include",
            });
            if (guestResponse.ok) await load();
          }
        } catch { /* stay on the login page */ }
      }
    })();
    fetch(`${API_BASE}/api/auth/demo-accounts`, { credentials: "include" })
      .then(async (response) => {
        if (!response.ok) return;
        const result = await response.json();
        setDemoAccounts(Array.isArray(result.accounts) ? result.accounts : []);
        setDemoAvailable(Array.isArray(result.accounts) && result.accounts.length > 0);
      }).catch(() => {});
  }, []);
  useEffect(() => {
    if (!authenticated || page === "change-password") return;
    refreshNotifications().catch(() => {});
  }, [authenticated, page]);
  useEffect(() => {
    const term = query.trim();
    const requestId = ++searchRequestId.current;
    if (!authenticated || !term || role === "hr") {
      setSearchMatches(null);
      setSearchResultIds([]);
      setSearchTruncated(false);
      setSearchStatus("idle");
      if (!term) setSearchActiveIndex(-1);
      return undefined;
    }
    let active = true;
    setSearchMatches(null);
    setSearchStatus("loading");
    setSearchTruncated(false);
    setSearchActiveIndex(-1);
    const timer = setTimeout(async () => {
      try {
        const response = await fetch(`${API_BASE}/api/households/search?q=${encodeURIComponent(term)}`, {
          credentials: "include",
        });
        if (!response.ok) throw new Error("search failed");
        const result = await response.json();
        if (active && requestId === searchRequestId.current) {
          const ids = Array.isArray(result.household_ids) ? result.household_ids : [];
          setSearchResultIds(ids);
          setSearchTruncated(Boolean(result.truncated));
          setSearchMatches(new Set(ids));
          setSearchStatus("success");
        }
      } catch {
        if (active && requestId === searchRequestId.current) {
          setSearchResultIds([]);
          setSearchTruncated(false);
          setSearchMatches(new Set());
          setSearchStatus("error");
        }
      }
    }, 250);
    return () => { active = false; clearTimeout(timer); };
  }, [query, authenticated, role, locale, searchRetry]);
  useEffect(() => {
    const closeOnOutsidePointer = (event) => {
      if (searchControlRef.current && !searchControlRef.current.contains(event.target)) setSearchOpen(false);
    };
    document.addEventListener("pointerdown", closeOnOutsidePointer);
    return () => document.removeEventListener("pointerdown", closeOnOutsidePointer);
  }, []);
  useEffect(() => { if (searchExpanded) searchInputRef.current?.focus(); }, [searchExpanded]);
  useEffect(() => {
    const closeAccountMenu = (event) => {
      if (accountMenuRef.current && !accountMenuRef.current.contains(event.target)) setAccountMenuOpen(false);
    };
    document.addEventListener("mousedown", closeAccountMenu);
    return () => document.removeEventListener("mousedown", closeAccountMenu);
  }, []);
  useEffect(() => {
    if (!toast) return undefined;
    const id = setTimeout(() => setToast(""), 3000);
    return () => clearTimeout(id);
  }, [toast]);
  useEffect(() => {
    if (!sampleMode || !authenticated) return undefined;
    const lockTextInputs = () => {
      document.querySelectorAll("input, textarea").forEach((el) => {
        if (el.closest(".searchbox") || el.closest(".login-card")) return;
        const type = (el.getAttribute("type") || "text").toLowerCase();
        if (type === "file") { el.disabled = true; return; }
        if (el.tagName === "TEXTAREA" || ["text", "search", "tel", "email", "url", "password"].includes(type)) {
          el.readOnly = true;
          el.setAttribute("data-sample-locked", "1");
        }
      });
      document.querySelectorAll('[contenteditable="true"]').forEach((el) => {
        el.setAttribute("contenteditable", "false");
      });
    };
    lockTextInputs();
    const observer = new MutationObserver(lockTextInputs);
    observer.observe(document.body, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, [sampleMode, authenticated, page, modal, data]);

  async function api(path, method = "POST", body) {
    setBusy(true);
    try {
      const response = await fetch(`${API_BASE}${path}`, {
        method, credentials: "include", headers: { "Content-Type": "application/json" },
        body: body ? JSON.stringify(body) : undefined,
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}));
        throw new Error(detail.detail || t("error"));
      }
      await load();
      setToast(t("success"));
      return await response.json();
    } catch (error) {
      setToast(error.message || t("error"));
      throw error;
    } finally { setBusy(false); }
  }

  async function login(path, body) {
    resetSearchState();
    setSearchExpanded(false);
    setAccountMenuOpen(false);
    setBusy(true);
    setLoginError("");
    try {
      const response = await fetch(`${API_BASE}${path}`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || t("error"));
      const identity = await load();
      setBusinessFilter("");
      if (!identity.user.must_change_password && identity.account_role !== "hr") {
        setPage(identity.account_role === "owner" ? "owner-portal" : "dashboard");
      }
    } catch (error) {
      setLoginError(error.message || t("error"));
    } finally { setBusy(false); }
  }

  async function logout() {
    resetSearchState();
    setSearchExpanded(false);
    setAccountMenuOpen(false);
    await fetch(`${API_BASE}/api/auth/logout`, { method: "POST", credentials: "include" });
    setAuthenticated(false);
    setData(null);
    setTasks([]);
    setNotifications([]);
    setNotificationUnreadCount(0);
    notificationRequestId.current += 1;
    setPage("dashboard");
  }
  function resetSearchState() {
    searchRequestId.current += 1;
    setQuery("");
    setSearchMatches(null);
    setSearchResultIds([]);
    setSearchTruncated(false);
    setSearchStatus("idle");
    setSearchRetry(0);
    setSearchOpen(false);
    setSearchActiveIndex(-1);
  }
  async function updateNotification(notification, action) {
    const response = await fetch(`${API_BASE}/api/notifications/${notification.id}/${action}`, {
      method: "PUT", credentials: "include",
    });
    if (!response.ok) throw new Error(t("error"));
    await refreshNotifications();
  }
  function openNotification(notification) {
    setNotificationCenterOpen(false);
    if (notification.related_record_type === "audit_outbox" && data.account_role !== "owner") {
      setPage("settings");
    }
  }

  const matchedTasks = useMemo(() => matchBusinessTasks(businessFilter, tasks), [businessFilter, tasks]);
  const terminalExcludedTaskCount = useMemo(() => {
    if (!isTaskBusinessFilter(businessFilter)) return 0;
    const householdStages = new Map((data?.households || []).map((household) => [household.id, household.stage_events.at(-1)?.to_stage]));
    return matchedTasks.filter((task) => TERMINAL_STAGES.includes(householdStages.get(task.household_id))).length;
  }, [businessFilter, matchedTasks, data]);
  const filtered = useMemo(() => {
    let rows = data?.households || [];
    if (query.trim()) {
      if (!searchMatches) return [];
      rows = rows.filter((household) => searchMatches.has(household.id));
    }
    if (businessFilter === "unassigned") rows = rows.filter((h) => !h.advisor_id || h.introductions.some((item) => !item.advisor_id));
    if (businessFilter === "validity:due") {
      const localDate = (date) => [
        date.getFullYear(),
        String(date.getMonth() + 1).padStart(2, "0"),
        String(date.getDate()).padStart(2, "0"),
      ].join("-");
      const now = new Date();
      const lastDay = new Date(now);
      lastDay.setDate(lastDay.getDate() + 30); // Matches the current sla.introduction_validity_days.
      const today = localDate(now);
      const limit = localDate(lastDay);
      rows = rows.filter((h) => h.introductions.some((item) => {
        const validUntil = item.valid_until?.toString().slice(0, 10);
        return validUntil && validUntil >= today && validUntil <= limit;
      }));
    }
    if (businessFilter === "disputed") rows = rows.filter((h) => h.introductions.some((item) => item.status === "帰属争議中" || item.entitlement_state === "Disputed"));
    if (isTaskBusinessFilter(businessFilter)) {
      const relevantIds = new Set(matchedTasks.map((task) => task.household_id).filter(Boolean));
      rows = rows.filter((h) => relevantIds.has(h.id) && !TERMINAL_STAGES.includes(h.stage_events.at(-1)?.to_stage));
    }
    return rows;
  }, [data, query, searchMatches, businessFilter, matchedTasks]);
  const searchHouseholds = searchResultIds.map((id) => data?.households?.find((household) => household.id === id)).filter(Boolean).slice(0, 5);
  const showSearchResults = Boolean(query.trim() && searchOpen);
  const searchFeedback = query.trim() && (
    searchStatus === "loading" ? <div className="search-result-message" role="status">
      <span className="spinner" aria-hidden="true"/>{t("searchLoading")}
    </div> : searchStatus === "error" && <div className="search-result-message search-result-error" role="alert">
      <span>{t("searchError")}</span>
      <button type="button" onClick={() => { setSearchStatus("loading"); setSearchRetry((n) => n + 1); }}>{t("searchRetry")}</button>
    </div>
  );
  function closeSearch() {
    setSearchOpen(false);
    setSearchExpanded(false);
    setSearchActiveIndex(-1);
    requestAnimationFrame(() => searchLaunchRef.current?.focus());
  }
  function handleSearchKeyDown(event) {
    if (event.key === "Escape") {
      if (searchOpen) {
        setSearchOpen(false);
        setSearchActiveIndex(-1);
      } else closeSearch();
      return;
    }
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      if (!query.trim()) return;
      event.preventDefault();
      setSearchOpen(true);
      const count = searchHouseholds.length;
      if (!count || searchStatus !== "success") return;
      setSearchActiveIndex((index) => event.key === "ArrowDown"
        ? (index + 1) % count : (index <= 0 ? count - 1 : index - 1));
      return;
    }
    if (event.key === "Enter") {
      event.preventDefault();
      if (searchStatus !== "success") return;
      if (searchActiveIndex >= 0 && searchHouseholds[searchActiveIndex]) {
        openHousehold(searchHouseholds[searchActiveIndex]);
        setSearchOpen(false);
      } else {
        setPage("households");
        setSearchOpen(false);
      }
    }
  }
  const openHousehold = (household) => { setSelected(household); setModal("household"); };
  function handleReminder(reminder, item) {
    setBusinessFilter(reminder.filter);
    setPage(reminder.target_page);
    if (reminder.target_page !== "introductions" || item?.id == null) return;
    const household = data.households.find((h) => h.introductions.some((intro) => intro.id === item.id));
    if (household) setIntroFocusHouseholdId(household.id);
  }
  if (!authenticated || !data) return <>{sampleMode && <SampleWatermark />}<LoginPage locale={locale} setLocale={setLocale} t={t} accounts={demoAccounts}
    demoAvailable={demoAvailable} error={loginError} busy={busy} onLogin={login}/></>;
  const navItems = data.account_role === "owner" ? rentalPages.slice(-1)
    : data.account_role === "hr" ? [["accounts", t("accounts")]]
      : [...rentalPages.filter(([id]) => id !== "owner-portal"), ["team", t("collaboration")], ["management", t("management")],
        ["settings", t("settings")],
        ...(data.account_role === "administrator" ? [["accounts", t("accounts")]] : [])];
  const homePage = navItems[0][0];

  return <div className="app-shell">
    {sampleMode && <div style={{ background: "#7c2d12", color: "#fff", padding: "6px 14px", fontSize: "12.5px", textAlign: "center" }}>
      共有サンプル環境：表示データはすべて架空です。ログイン不要で操作を試せますが、文字入力は無効化され、データは毎日自動リセットされます。
    </div>}
    {sampleMode && <SampleWatermark />}
    <header className="app-bar"><button className="app-brand" onClick={() => { setWorkspaceView("home"); setPage(homePage); }}><span className="brand-mark"><Home size={20}/></span><span><b>SumaiBoard</b><small>賃貸管理業務</small></span></button>
      <div className="top-actions">
        {["households", "introductions", "revenue"].includes(page) && (!searchExpanded
          ? <button type="button" className="search-launch" ref={searchLaunchRef} aria-expanded={false}
              onClick={() => setSearchExpanded(true)}><Search size={16}/>{t("search")}</button>
          : <div className="search-control" ref={searchControlRef}
              onBlur={(event) => {
                if (!event.currentTarget.contains(event.relatedTarget) && !query.trim() && !searchOpen) setSearchExpanded(false);
              }}>
              <div className="searchbox">
                <Search size={16} aria-hidden="true"/>
                <input ref={searchInputRef} value={query} aria-label={t("search")} role="combobox" aria-autocomplete="list"
                  aria-expanded={showSearchResults} aria-controls={showSearchResults ? "global-search-options" : undefined}
                  aria-activedescendant={showSearchResults && searchActiveIndex >= 0 ? `search-option-${searchActiveIndex}` : undefined}
                  onFocus={() => { if (query.trim()) setSearchOpen(true); }} onKeyDown={handleSearchKeyDown}
                  onChange={(event) => {
                    const value = event.target.value;
                    searchRequestId.current += 1;
                    setQuery(value);
                    setSearchOpen(Boolean(value.trim()));
                    setSearchActiveIndex(-1);
                    setSearchMatches(null);
                    setSearchResultIds([]);
                    setSearchTruncated(false);
                    setSearchStatus(value.trim() ? "loading" : "idle");
                  }} placeholder={t("search")}/>
                {query && <button type="button" className="search-clear" aria-label={t("clearSearch")} title={t("clearSearch")}
                  onMouseDown={(event) => event.preventDefault()} onClick={() => {
                    resetSearchState();
                    searchInputRef.current?.focus();
                  }}><X size={14}/></button>}
                <button type="button" className="search-close" aria-label={t("close")} title={t("close")} onClick={closeSearch}><ChevronUp size={16}/></button>
              </div>
              {showSearchResults && <div className="global-search-results">
                {searchFeedback}
                {searchStatus === "success" && <>
                  <div className="search-result-summary">{t("searchCount")(searchResultIds.length, searchTruncated)}</div>
                  {searchResultIds.length === 0 && <div className="search-empty">
                    <strong>{t("searchNoResults")}</strong><span>{t("searchNoResultsHint")}</span>
                  </div>}
                </>}
                <div id="global-search-options" role="listbox" aria-label={t("search")}>
                  {searchStatus === "success" && searchHouseholds.map((household, index) => <button type="button" role="option"
                    id={`search-option-${index}`} aria-selected={index === searchActiveIndex}
                    className={`search-result-option${index === searchActiveIndex ? " active" : ""}`}
                    key={household.id} onMouseEnter={() => setSearchActiveIndex(index)} onClick={() => {
                      openHousehold(household);
                      setSearchOpen(false);
                      setSearchActiveIndex(-1);
                    }}>
                    <span className="search-result-code">{household.household_code || `#${household.id}`}</span>
                    <span className="search-result-details">
                      <strong>{household.representative_name || "—"}</strong>
                      <small>{household.representative_kana || household.kana || household.persons?.[0]?.kana || "—"}</small>
                    </span>
                    <span className="search-result-phone">{household.phone || household.phone_number || household.persons?.[0]?.phone || "—"}</span>
                  </button>)}
                </div>
                {searchStatus === "success" && <>
                  {searchTruncated && <div className="search-truncated">{t("searchTruncated")}</div>}
                  {searchResultIds.length > 0 && <button type="button" className="search-view-all" onClick={() => {
                    setPage("households");
                    setSearchOpen(false);
                    setSearchActiveIndex(-1);
                  }}>{t("searchViewAll")(searchResultIds.length)}<ChevronRight size={14}/></button>}
                </>}
              </div>}
            </div>)}
        {data.account_role !== "owner" && <div className="notification-anchor"><button type="button" className="icon-btn" title={t("notifications")}
          aria-label={t("notifications")} aria-expanded={notificationCenterOpen} onClick={() => {
            setNotificationCenterOpen(!notificationCenterOpen);
            refreshNotifications().catch(() => {});
          }}><Bell size={18}/></button>{notificationCenterOpen && <NotificationCenter items={notifications}
          unreadCount={notificationUnreadCount} locale={locale} t={t} onOpen={openNotification}
          onRead={(item) => updateNotification(item, "read")} onArchive={(item) => updateNotification(item, "archive")}/>}</div>}
      <div className="account-menu-wrap" ref={accountMenuRef}><button type="button" className="account-menu-button" aria-label={t("account")} aria-expanded={accountMenuOpen} onClick={() => setAccountMenuOpen((v)=>!v)}><span className="avatar">{role === "hq_finance" ? "\u7d4c" : role === "manager" ? "\u5e97" : "\u4f50"}</span><span className="role-meta"><b>{data.user?.name || "\u2014"}</b><small>{roleLabel(locale, data.account_role || role)}</small></span><ChevronDown size={16}/></button>{accountMenuOpen && <div className="account-menu-panel"><div className="account-menu-identity"><b>{data.user?.name || "\u2014"}</b><span>{roleLabel(locale, data.account_role || role)}</span></div>{demoAvailable && <div className="select-wrap"><Users size={15}/><select aria-label={t("account")} value={data.user.id} onChange={(event) => login("/api/auth/demo-login", { account_id: Number(event.target.value) })}>{demoAccounts.map((option) => <option value={option.id} key={option.id}>{option.display_name} · {roleLabel(locale, option.role)}{option.store_id ? ` \u00b7 ${option.store_id}` : ""}</option>)}</select><ChevronDown size={13}/></div>}<button className="language-btn" onClick={() => setLocale(locale === "ja" ? "zh" : "ja")} title={t("language")}><Languages size={16}/>{locale === "ja" ? "\u4e2d\u6587" : "\u65e5\u672c\u8a9e"}</button><button className="account-signout" onClick={logout}><LogOut size={16}/>{sampleMode ? "管理者ログイン" : t("signOut")}</button></div>}</div></div>
    </header><main className="page-main"><div className="page-content">{!data ? <div className="loading"><div className="spinner"/>Loading SumaiBoard\u2026</div> : <>
      {page === "accounts" && ["hr","administrator"].includes(data.account_role) && <AccountsPage accounts={data.accounts || []} locale={locale} t={t} api={api}/>}
      {page === "change-password" && <PasswordChangePage forced api={api} t={t} onChanged={() => setPage(data.account_role === "hr" ? "accounts" : "dashboard")}/>}
      {page !== "change-password" && <nav className="rental-nav" aria-label="業務メニュー">
        {navItems.map(([id, label]) => <button className="secondary-btn" type="button" key={id}
          aria-current={page === id ? "page" : undefined}
          onClick={() => { setWorkspaceView("home"); setPage(id); }}>{label}</button>)}
      </nav>}
      <RentalPage
        key={`${data.user.id}:${page}`}
        page={page}
        apiBase={API_BASE}
        accountRole={data.account_role}
        userId={data.user.id}
        view={workspaceView}
        onNavigate={(target, view = "home") => { setWorkspaceView(view); setPage(target); }}
      />
      {page === "households" && <Households locale={locale} items={filtered} stores={data.stores} t={t} onOpen={openHousehold} businessFilter={businessFilter} matchedTasks={matchedTasks} terminalExcludedTaskCount={terminalExcludedTaskCount} onClearBusinessFilter={() => setBusinessFilter("")} searchFeedback={searchFeedback}/>}
      {page === "introductions" && <Introductions locale={locale} items={filtered} t={t} onOpen={openHousehold}
        onAdd={(household)=>{setSelected(household);setModal("introduction");}} businessFilter={businessFilter}
        onClearBusinessFilter={() => setBusinessFilter("")} focusHouseholdId={introFocusHouseholdId}
        onFocusHandled={() => setIntroFocusHouseholdId(null)} searchFeedback={searchFeedback}/>}
      {page === "revenue" && <Revenue data={data} t={t} role={role} api={api} onOpen={openHousehold} filter={businessFilter} onClearBusinessFilter={() => setBusinessFilter("")}/>}
      {page === "team" && <section><PageTitle eyebrow={t("collaboration")} title={t("collaboration")}/><div className="trend-controls team-view-tabs">{[["calendar","schedule"],["bulletin","bulletin"]].map(([view,label])=>{const active=workspaceView===view||(workspaceView==="home"&&view==="calendar");return <button className={`secondary-btn view-tab${active?" is-active":""}`} aria-pressed={active} key={view} onClick={()=>setWorkspaceView(view)}>{t(label)}</button>;})}</div><CollaborationWorkspace displayDate={displayDate} roleLabel={roleLabel} stageLabel={localeLabel} view={workspaceView==="home"?"calendar":workspaceView} data={data} locale={locale} role={role} t={t} api={api} onBack={() => { setWorkspaceView("home"); setPage("dashboard"); }} onTask={()=>{}} onHousehold={openHousehold}/></section>}
      {page === "management" && <div className="admin-page management-page">
        <PageTitle title={t("management")}/>
        <AuditTrailPanel t={t} userId={data.user.id} locale={locale}/>
        {!sampleMode && <MonthClosePanel accountRole={data.account_role} userId={data.user.id} t={t}/>}
      </div>}
      {page === "settings" && <SettingsPage data={data} t={t} role={role} locale={locale} onLocaleChange={setLocale} onReset={async()=>{if(window.confirm(t("resetConfirm"))){await api("/api/reset");setToast(t("resetDone"));}}} onConfigSaved={()=>{load().catch(()=>setToast("API connection failed"));setToast(t("configSaved"));}} preferences={preferences} onSavePreferences={(next)=>api("/api/preferences","PUT",next)} sampleMode={sampleMode}/>}
    </>}<footer className="app-footer"><ShieldCheck size={14}/>{t("prototype")} ? {t("demoWarning")}<span>{t("copyright")}</span></footer></div></main>
    {modal === "household" && selected && <HouseholdModal locale={locale} household={selected} t={t} role={role}
      onClose={() => setModal("")} onActivity={() => setModal("activity")} api={api}/>}
    {modal === "activity" && <ActivityModal households={data?.households || []} initialHouseholdId={selected?.id} t={t} onClose={() => setModal("")}
      onSubmit={(body) => api("/api/activities", "POST", body)}/>}
    {modal === "introduction" && selected && <IntroductionModal household={selected} data={data} t={t}
      onClose={() => setModal("")} onSubmit={(body) => api("/api/introductions", "POST", body)}/>}
    {toast && <div className={`toast ${toast === t("error") ? "toast-error" : ""}`}><Check size={17}/>{toast}</div>}
    {busy && <div className="busy-indicator"><div className="spinner"/></div>}
  </div>;
}

function ModuleEntries({navItems,accountRole,t,onNavigate}) { const desc={households:"descHouseholds",introductions:"descIntroductions",revenue:"descRevenue",team:"descTeam",management:"descManagement",settings:"descSettings",accounts:"descAccounts"}; const tone={households:"blue",introductions:"violet",revenue:"green",team:"amber",management:"blue",settings:"neutral",accounts:"violet"}; const items=navItems.filter(([id])=>id!=="dashboard"), ordinary=items.filter(([id])=>id!=="accounts"), accounts=items.filter(([id])=>id==="accounts"); const cards=(list)=>list.map(([id,Icon,key])=><button type="button" className="module-entry" key={id} onClick={()=>onNavigate(id)}><span className={`module-entry-icon tone-${tone[id]}`}><Icon size={19}/></span><b>{t(key)}</b><small>{t(desc[id])}</small></button>); return <div className="module-entries"><h2>{t("workspace")}</h2><div className="module-entry-grid">{cards(ordinary)}</div>{accountRole==="administrator"&&accounts.length>0&&<section className="system-management"><h2>{t("systemManagement")}</h2><div className="module-entry-grid">{cards(accounts)}</div></section>}</div>; }

function PageTitle({ eyebrow, title, sub, actions }) {
  return <div className="page-title"><div>{eyebrow && <div className="eyebrow">{eyebrow}</div>}<h1>{title}</h1>{sub && <p>{sub}</p>}</div>{actions && <div className="title-actions">{actions}</div>}</div>;
}
function Metric({ label, value, delta, icon: Icon, tone = "blue", small }) {
  return <div className={`metric-card ${small ? "metric-small" : ""}${tone === "emphasis" ? " metric-emphasis" : ""}`}><div className={`metric-icon ${tone}`}><Icon size={18}/></div>
    <div className="metric-info"><span>{label}</span><strong>{value}</strong>{delta && <small>{delta}</small>}</div>
    {delta && <div className="metric-spark"><ArrowUpRight size={16}/></div>}</div>;
}
function NotificationCenter({ items, unreadCount, locale, t, onOpen, onRead, onArchive }) {
  const [error, setError] = useState("");
  async function act(event, callback, item) {
    event.stopPropagation();
    setError("");
    try { await callback(item); }
    catch (requestError) { setError(requestError.message || t("error")); }
  }
  return <section className="notification-center" role="dialog" aria-label={t("notifications")}>
    <header><b>{t("notifications")}</b><span>{t("unreadNotifications")}: {unreadCount}</span></header>
    {error && <p className="config-error" role="alert">{error}</p>}
    {items.length === 0 ? <p className="notification-empty">{t("noNotifications")}</p> :
      <div className="notification-list">{items.map((item) => <article className={`notification-item ${item.status.toLowerCase()}`}
        key={item.id}>
        <button className="notification-open" onClick={() => onOpen(item)}>
          <small className="notification-type">{t(`notification${item.notification_type}`) || item.notification_type}</small>
          <strong>{locale === "zh" && item.title_zh ? item.title_zh : item.title}</strong>
          <span>{locale === "zh" && item.message_zh ? item.message_zh : item.message}</span>
          <small>{displayDate(item.created_at)}</small>
        </button>
        <div className="notification-actions">
          {item.status === "UNREAD" && <button onClick={(event) => act(event, onRead, item)}>{t("markRead")}</button>}
          {item.status === "READ" && <button onClick={(event) => act(event, onArchive, item)}>{t("archiveNotification")}</button>}
        </div>
      </article>)}</div>}
  </section>;
}

function SampleWatermark() {
  return <div className="sample-watermark" aria-hidden="true" />;
}
function LoginPage({ locale, setLocale, t, accounts, demoAvailable, error, busy, onLogin }) {
  const [accountId, setAccountId] = useState(accounts[0]?.id || "");
  const [employeeCode, setEmployeeCode] = useState("");
  const [password, setPassword] = useState("");
  useEffect(() => {
    if (!accounts.some((account) => String(account.id) === String(accountId))) {
      setAccountId(accounts[0]?.id || "");
    }
  }, [accounts, accountId]);
  return <main className="login-shell">
    <section className="login-card">
      <div className="brand-mark"><Home size={21}/></div>
      <p className="eyebrow">SumaiBoard</p><h1>{t("loginTitle")}</h1><p>{t("loginSubtitle")}</p>
      {demoAvailable && <form onSubmit={(event) => {
        event.preventDefault();
        if (accountId) onLogin("/api/auth/demo-login", { account_id: Number(accountId) });
      }}>
        <label>{t("account")}<select value={accountId} onChange={(event) => setAccountId(event.target.value)}>
          {accounts.map((account) => <option key={account.id} value={account.id}>
            {account.display_name} · {roleLabel(locale, account.role)}
          </option>)}
        </select></label>
        <button className="primary-btn login-submit" disabled={busy || !accountId}>{t("demoLogin")}</button>
      </form>}
      <form onSubmit={(event) => {
        event.preventDefault();
        if (!password) return;
        onLogin("/api/auth/login", { employee_code: employeeCode, password });
      }}>
        <label>{t("employeeCode")}<input autoComplete="username" value={employeeCode}
          onChange={(event) => setEmployeeCode(event.target.value)} required/></label>
        <label>{t("password")}<input autoComplete="current-password" type="password" value={password}
          onChange={(event) => setPassword(event.target.value)} required/></label>
        <button className="secondary-btn login-submit" disabled={busy || !password}>{t("signIn")}</button>
      </form>
      {error && <div className="config-error" role="alert">{error}</div>}
      <button className="language-btn" onClick={() => setLocale(locale === "ja" ? "zh" : "ja")}
        type="button">{locale === "ja" ? "中文" : "日本語"}</button>
      <footer>{t("prototype")} · {t("demoWarning")}</footer>
    </section>
  </main>;
}

function AccountsPage({ accounts, locale, t, api }) {
  const [selectedId, setSelectedId] = useState("");
  const [method, setMethod] = useState("in_person");
  const [resetToken, setResetToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [resetError, setResetError] = useState(false);
  async function issueReset() {
    if (!selectedId) return;
    setResetError(false);
    setBusy(true);
    try {
      const result = await api("/api/auth/password-reset-requests", "POST",
        { user_id: Number(selectedId), verification_method: method });
      setResetToken(result.reset_token);
    } catch {
      setResetError(true);
    } finally { setBusy(false); }
  }
  return <div className="admin-page accounts-page"><PageTitle eyebrow={t("accounts")} title={t("accounts")} sub={t("resetRequest")}/>
    <section className="panel account-reset-panel"><div className="panel-head"><h2>{t("resetPanelTitle")}</h2></div><div className="account-reset-form">
      <label>{t("account")}<select value={selectedId} onChange={(event) => setSelectedId(event.target.value)}>
        <option value="">—</option>{accounts.map((account) => <option value={account.id} key={account.id}>
          {account.display_name} · {account.employee_code}</option>)}
      </select></label>
      <label>{t("verificationMethod")}<select value={method} onChange={(event) => setMethod(event.target.value)}>
        <option value="in_person">{t("inPerson")}</option><option value="video_call">{t("verifiedCall")}</option>
        <option value="identity_checked">{t("identityChecked")}</option>
      </select></label>
      <button className="primary-btn" disabled={busy || !selectedId} onClick={issueReset}>{t("requestReset")}</button>
      {resetToken && <label className="reset-token-field">{t("resetLink")}<input readOnly value={resetToken}/></label>}
    </div>{resetError && <p className="config-error" role="alert">{t("resetRequestFailed")}</p>}</section>
    <section className="panel table-panel"><div className="panel-head"><h2>{t("accounts")} <span className="count-badge">{accounts.length}</span></h2></div>
      <div className="table-scroll"><table><thead><tr><th>{t("employeeCode")}</th><th>{t("account")}</th>
        <th>{t("role")}</th><th>{t("accountStatus")}</th><th>{t("lastLogin")}</th></tr></thead>
        <tbody>{accounts.map((account) => <tr key={account.id}><td>{account.employee_code}</td>
          <td>{account.display_name}</td><td>{roleLabel(locale, account.role)}</td>
          <td><AccountStatus status={account.account_status} locale={locale}/></td><td>{displayDate(account.last_login_at)}</td></tr>)}</tbody></table>{!accounts.length && <div className="empty-state">{t("noAccounts")}</div>}
      </div>
    </section>
  </div>;
}

function PasswordChangePage({ forced = false, api, t, onChanged }) {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState("");
  async function submit(event) {
    event.preventDefault();
    if (newPassword !== confirmation) {
      setError(t("passwordMismatch"));
      return;
    }
    try {
      await api("/api/auth/change-password", "POST",
        { current_password: forced ? null : currentPassword, new_password: newPassword });
      onChanged();
    } catch (requestError) {
      setError(requestError.message || t("error"));
    }
  }
  return <section className="panel change-password-panel"><h1>{t("changePasswordTitle")}</h1>
    <form onSubmit={submit}>
      {!forced && <label>{t("currentPassword")}<input type="password" autoComplete="current-password"
        value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} required/></label>}
      <label>{t("newPassword")}<input type="password" autoComplete="new-password" value={newPassword}
        onChange={(event) => setNewPassword(event.target.value)} minLength={12} required/></label>
      <label>{t("confirmPassword")}<input type="password" autoComplete="new-password" value={confirmation}
        onChange={(event) => setConfirmation(event.target.value)} minLength={12} required/></label>
      {error && <div className="config-error" role="alert">{error}</div>}
      <button className="primary-btn" type="submit">{t("changePassword")}</button>
    </form>
  </section>;
}

const AUDIT_BUSINESS_ACTIONS = new Set([
  "activity.created", "calendar_event.created", "calendar_event.updated",
  "negotiation.next_action.updated", "introduction.created", "construction.confirmed",
  "referral_dispute.raised", "referral_dispute.decided", "stage.changed", "daily_report.saved",
]);
const AUDIT_BUSINESS_PREFIXES = ["bulletin.", "entitlement.", "expense."];
function auditCategory(action) {
  if (action === "DEMO_ROLE_SWITCH") return "system";
  if (AUDIT_BUSINESS_ACTIONS.has(action) || AUDIT_BUSINESS_PREFIXES.some((prefix) => String(action || "").startsWith(prefix))) return "business";
  return "audit";
}

function EmployeeWorkstation({ locale, data, tasks, t, onActivity, onView, onTask, onOpenTasks }) {
  const today = todayJst();
  const dueToday = tasks.filter((task) => String(task.due_at).slice(0, 10) <= today).length;
  const overdue = tasks.filter((task) => task.days_overdue > 0).length;
  const dueSoon = tasks.filter((task) => {
    const due = new Date(`${String(task.due_at).slice(0, 10)}T00:00:00`);
    const days = Math.ceil((due - new Date(`${today}T00:00:00`)) / 86400000);
    return days >= 0 && days <= 3;
  }).length;
  const householdById = new Map((data.households || []).map((household) => [String(household.id), household]));
  const recentLogs = (data.audit_logs || []).slice(0, 5);
  return <div className="employee-workstation">
    <PageTitle title={<>{t("workToday")}<span>{data.user.name}{locale === "ja" && t("greetingSuffix")}</span></>}
      sub={t("todaySub")} eyebrow={displayDate(today)}/>
    <div className="employee-card-grid">
      <button className="employee-action-card tone-blue" onClick={() => onOpenTasks("tasks:today_followups")}>
        <span>{t("workToday")}</span><strong>{dueToday}</strong><small>{t("todayWorkCount")}</small>
        <b>{t("openTodayWork")} <ChevronRight size={14}/></b>
      </button>
      <button className="employee-action-card tone-amber" onClick={() => onOpenTasks("tasks:overdue")}>
        <span>{t("deadlineReminder")}</span><strong>{overdue + dueSoon}</strong><small>{t("deadlineBreakdown").replace("{overdue}", overdue).replace("{dueSoon}", dueSoon)}</small>
        <b>{t("openOverdue")} <ChevronRight size={14}/></b>
      </button>
      <section className="employee-action-card tone-green">
        <span>{t("businessRegistration")}</span><strong className="card-icon"><Plus size={22}/></strong>
        <small>{t("createActivity")}</small>
        <div className="employee-card-actions">
          <button onClick={onActivity}>{t("createActivity")}</button>
          <button onClick={() => onView("expenses")}>{t("createExpense")}</button>
        </div>
      </section>
      <button className="employee-action-card tone-violet" onClick={() => onView("records")}>
        <span>{t("workHistory")}</span><strong className="card-icon"><FileText size={22}/></strong>
        <small>{data.daily_report?.report_date ? displayDate(data.daily_report.report_date) : t("dailyReport")}</small>
        {data.daily_report?.auto_summary && <SummaryText className="work-history-summary" summary={data.daily_report.auto_summary} t={t} locale={locale}/>}
        <b>{t("openWorkHistory")} <ChevronRight size={14}/></b>
      </button>
    </div>
    <section className="panel employee-task-panel">
      <div className="panel-head"><div><div className="eyebrow">{t("actionRequired")}</div><h2>{t("taskQueues")}</h2></div>
        <span className="pill pill-blue">{tasks.length}</span></div>
      {tasks.length ? tasks.slice(0, 8).map((task) => <button className="employee-task-row" key={task.task_id}
        onClick={() => onTask(task)}>
        <span className={`task-check ${task.days_overdue > 0 ? "text-danger" : ""}`}>
          {task.priority === "high" ? <CircleAlert size={16}/> : <Clock3 size={16}/>}</span>
        <span className="employee-task-copy"><b>{task.title}</b>
          {householdById.has(String(task.household_id)) && <small>{householdById.get(String(task.household_id)).representative_name}{householdById.get(String(task.household_id)).household_code ? ` · ${householdById.get(String(task.household_id)).household_code}` : ""}</small>}
          <small>{displayDate(task.due_at)}{task.days_overdue > 0 ? ` · ${task.days_overdue} ${t("daysOverdue")}` : ""}</small></span>
        <span className={`pill ${task.days_overdue > 0 ? "pill-red" : task.status === "in_progress" ? "pill-blue" : "pill-amber"}`}>
          {task.days_overdue > 0 ? t("overdueLabel") : task.status === "in_progress" ? t("inProgressTask") : t("pendingTask")}</span><ChevronRight size={15}/>
      </button>) : <div className="empty-mini"><Check size={17}/>{t("noPendingTasks")}</div>}
    </section>
    <section className="panel employee-recent-panel">
      <div className="panel-head"><div><div className="eyebrow">{t("recentActivity")}</div><h2>{t("recentActivity")}</h2></div></div>
      {recentLogs.length ? <div className="employee-recent-list">{recentLogs.map((log) => { const cat = auditCategory(log.action); return <article className="employee-recent-row" key={log.id}>
        <span className="recent-action"><b>{log.action === "DEMO_ROLE_SWITCH" ? t("auditDemoRoleSwitch") : log.action}</b><span className={`audit-chip audit-chip-${cat}`}>{t(cat === "system" ? "auditCatSystem" : cat === "business" ? "auditCatBusiness" : "auditCatAudit")}</span></span>
        {(log.target_type || log.target_id_text) && <span>{[log.target_type, log.target_id_text].filter(Boolean).join(" · ")}</span>}
        <time>{displayDate(log.at)}</time>
      </article>;})}</div> : <div className="empty-mini">{t("noRecentActivity")}</div>}
    </section>
    <section className="panel collaboration-shortcuts">
      <div className="panel-head"><div><div className="eyebrow">{t("collaboration")}</div><h2>{t("collaboration")}</h2></div></div>
      <div className="collaboration-shortcut-list">
        <button onClick={() => onView("calendar")}><CalendarDays size={17}/>{t("schedule")}</button>
        <button onClick={() => onView("bulletin")}><ClipboardList size={17}/>{t("bulletin")}</button>
        <button onClick={() => onView("queue")}><ArrowDownRight size={17}/>{t("negotiationQueue")}</button>
      </div>
    </section>
  </div>;
}

function EmployeeWorkHistory({ locale, data, t, api }) {
  const [note, setNote] = useState(data.daily_report?.manual_note || "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  async function save(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try { await api("/api/report", "PUT", { manual_note: note }); }
    catch (saveError) { setError(saveError.message || t("error")); }
    finally { setSaving(false); }
  }
  return <section className="panel employee-records">
    <div className="panel-head"><div><div className="eyebrow">{t("workHistory")}</div><h2>{t("dailyReport")}</h2></div></div>
    <div className="auto-summary"><div className="summary-icon"><Activity size={16}/></div>
      <div><span>{t("autoSummary")}</span><SummaryText summary={data.daily_report?.auto_summary} t={t} locale={locale}/></div></div>
    <form onSubmit={save}><label className="field-label">{t("note")}
      <textarea value={note} onChange={(event) => setNote(event.target.value)} rows="5"/></label>
      {error && <div className="config-error" role="alert">{error}</div>}
      <button className="primary-btn" disabled={saving}>{saving ? "…" : t("save")}</button>
    </form>
  </section>;
}

function Dashboard({ data, summary, tasks, preferences, t, role, locale, workspaceView,
  onWorkspaceView, api, onHousehold, onActivity, onNavigate, onReport, onCounter, onTask }) {
  const [note, setNote] = useState(data.daily_report?.manual_note || "");
  const [period, setPeriod] = useState("7d");
  const [metric, setMetric] = useState("introductions");
  const showManagement = role !== "advisor";
  if (workspaceView !== "home") {
    if (workspaceView === "expenses") {
      return <><PageTitle eyebrow={t("businessRegistration")} title={t("expenses")}
        actions={<button className="secondary-btn" onClick={() => onWorkspaceView("home")}>{t("backToWorkspace")}</button>}/>
        <ExpensePanel data={data} t={t} role={role} accountRole={data.account_role} locale={locale}/>
      </>;
    }
    if (workspaceView === "records") {
      return <><PageTitle eyebrow={t("workHistory")} title={t("dailyReport")}
        actions={<button className="secondary-btn" onClick={() => onWorkspaceView("home")}>{t("backToWorkspace")}</button>}/>
        <EmployeeWorkHistory locale={locale} data={data} t={t} api={api}/></>;
    }
    return <CollaborationWorkspace displayDate={displayDate} roleLabel={roleLabel} stageLabel={localeLabel} view={workspaceView} data={data} locale={locale} role={role} t={t}
      api={api} onBack={() => onWorkspaceView("home")} onTask={onTask} onHousehold={onHousehold}/>;
  }
  if (role === "advisor") {
    return <EmployeeWorkstation locale={locale} data={data} tasks={tasks} t={t} onActivity={onActivity}
      onView={(view) => onWorkspaceView(view)} onTask={onTask}
      onOpenTasks={(filter) => { onCounter({ filter, target_page: "households" }); }}/>;
  }
  const visibleTasks = tasks.slice(0, 5);
  if ((role === "manager" || role === "executive") && data.account_role !== "administrator") return <DashboardCockpit locale={locale} data={data} summary={summary} tasks={tasks} visibleTasks={visibleTasks} metric={metric} setMetric={setMetric} period={period} setPeriod={setPeriod} preferences={preferences} role={role} t={t} onActivity={onActivity} onNavigate={onNavigate} onReport={onReport} onCounter={onCounter} onTask={onTask}/>;
  return <><PageTitle eyebrow={displayDate(todayJst())}
    title={<>{t("todayTitle")}<span>{data.user.name}{locale === "ja" && t("greetingSuffix")}</span></>} sub={t("todaySub")}
    actions={<button className="primary-btn" onClick={onActivity}><Plus size={16}/>{t("quickActivity")}</button>}/>
    <section className="panel queue-panel"><div className="panel-head"><div><div className="eyebrow">{t("actionQueue")}</div><h2>{t("taskQueues")}</h2></div>
      {summary && <span className="muted">{displayDate(summary.generated_at)}</span>}</div>
      <div className="queue-counters">{(summary?.counters || []).slice(0, 3).map((counter) =>
        <button className={`queue-counter ${counter.key === "overdue" || counter.key === "critical_risk" ? "queue-danger" : ""}`}
          key={counter.key} onClick={() => onCounter(counter)}>
          <span>{t(`counter_${counter.key}`) || counter.label}</span><strong>{counter.count}</strong>
          <small>{counter.unit_type === "items" ? t("unitItems") : counter.unit_type}</small><ChevronRight size={15}/>
        </button>)}</div>
    </section>
    <div className="dashboard-grid">
      {preferences.dashboard_widgets.includes("tasks") && <section className="panel tasks-panel"><div className="panel-head"><div><div className="eyebrow">{t("actionRequired")}</div><h2>{t("taskQueues")}</h2></div>
        <span className="pill pill-red">{tasks.length}</span></div>
        {visibleTasks.length ? visibleTasks.map((task) => <div className="task-row" key={task.task_id}>
          <div className={`task-check ${task.days_overdue > 0 ? "text-danger" : ""}`}>
            {task.priority === "high" ? <CircleAlert size={16}/> : <Clock3 size={16}/>}</div>
          <div className="task-copy"><b>{task.title}</b><span>{displayDate(task.due_at)} · {task.days_overdue > 0 ? `${task.days_overdue} ${t("daysOverdue")}` : t("today")}</span></div>
          <button className="icon-btn compact" aria-label={t("open")} onClick={() => onTask(task)}><ChevronRight size={16}/></button>
        </div>) : <div className="empty-mini"><Check size={17}/>{t("noPendingTasks")}</div>}
        <div className="task-bottom"><span><Clock3 size={14}/>{t("overdueLabel")}</span>
          <button className="text-button" onClick={() => onNavigate(role === "hq_finance" ? "revenue" : "households")}>{t("viewAll")} <ChevronRight size={14}/></button></div>
      </section>}
      {showManagement && preferences.dashboard_widgets.includes("trend") ? <section className="panel pipeline-panel"><div className="panel-head"><div><div className="eyebrow">{t("businessTrend")}</div><h2>{t("trendEntry")}</h2></div>
        <button className="text-button" onClick={() => onNavigate("management")}>{t("viewAll")} <ChevronRight size={15}/></button></div>
        <div className="trend-controls"><select aria-label={t("selectMetric")} value={metric} onChange={(event) => setMetric(event.target.value)}>
          <option value="inquiries">{localeLabel(locale, "inquiries")}</option>
          <option value="visits">{localeLabel(locale, "visits")}</option>
          <option value="introductions">{localeLabel(locale, "introductions")}</option>
          <option value="contracts">{localeLabel(locale, "contracts")}</option>
          <option value="construction">{localeLabel(locale, "construction")}</option>
        </select><select aria-label={t("period")} value={period} onChange={(event) => setPeriod(event.target.value)}>
          <option value="7d">7d</option><option value="30d">30d</option><option value="90d">90d</option>
        </select></div>
        <TrendResult key={`${data.user.id}:${role}:${metric}:${period}`} metric={metric} period={period} locale={locale} t={t} chart="workstation"/>
      </section> : preferences.dashboard_widgets.includes("report") && <section className="panel report-panel"><div className="panel-head"><div><div className="eyebrow">{t("dailySummary")}</div><h2>{t("dailyReport")}</h2></div><FileText size={17} className="muted"/></div>
        <div className="auto-summary"><div className="summary-icon"><Activity size={16}/></div><div><span>{t("autoSummary")}</span><SummaryText summary={data.daily_report?.auto_summary} t={t} locale={locale}/></div></div>
        <label className="field-label">{t("note")}<textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="..." rows="3"/></label>
        <button className="secondary-btn full-width" onClick={() => onReport(note)}><Check size={15}/>{t("save")}</button>
      </section>}
    </div>
    {showManagement && preferences.dashboard_widgets.includes("overview") && <section className="panel household-panel">
      <div className="panel-head"><div><div className="eyebrow">{t("businessOverview")}</div><h2>{t("pipeline")}</h2></div>
        <button className="text-button" onClick={() => onNavigate("management")}>{t("viewAll")} <ChevronRight size={15}/></button></div>
      <small className="muted">{t("currentStageDistribution")}</small>
      <div className="pipeline-summary"><div><strong>{data.households.length}</strong><span>{t("households")}</span></div>
        <div className="pipeline-divider"/><div><strong>{data.households.reduce((count, item) => count + item.introductions.length, 0)}</strong><span>{t("introductions")}</span></div>
        <div className="pipeline-divider"/><div><strong>{data.entitlements.length}</strong><span>{t("entitlement")}</span></div></div>
      <StageFunnel items={data.households} locale={locale}/></section>}
  </>;
}
function DashboardCockpit({ locale, data, summary, tasks, visibleTasks, metric, setMetric, period, setPeriod, preferences, role, t, onActivity, onNavigate, onReport, onCounter, onTask }) {
  const [note, setNote] = useState(data.daily_report?.manual_note || "");
  const intros = data.households.reduce((count, item) => count + item.introductions.length, 0);
  const cockpitHeader = <><PageTitle eyebrow={displayDate(todayJst())} title={<>{t(role === "executive" ? "executiveTitle" : "managerTitle")}<span>{data.user.name}{locale === "ja" && t("greetingSuffix")}</span></>} sub={t(role === "executive" ? "executiveSub" : "managerSub")} actions={<button className="primary-btn" onClick={onActivity}><Plus size={16}/>{t("quickActivity")}</button>}/>
    <div className="cockpit-counters">{summary && <div className="cockpit-generated muted">{displayDate(summary.generated_at)}</div>}<div className="cockpit-counter-grid">{(summary?.counters || []).slice(0, 3).map((counter) => { const danger = counter.key === "overdue" || counter.key === "critical_risk"; return <button key={counter.key} className={`cockpit-counter${danger ? " cockpit-danger" : ""}`} onClick={() => onCounter(counter)}><span>{t(`counter_${counter.key}`) || counter.label}</span><strong>{counter.count}</strong><small>{counter.unit_type === "items" ? t("unitItems") : counter.unit_type}</small><ChevronRight size={17}/></button>; })}</div></div></>;
  const tasksBlock = (
    <section className="panel cockpit-tasks"><div className="panel-head"><div><div className="eyebrow">{t("actionRequired")}</div><h2>{t("taskQueues")}</h2></div><span className="pill pill-red">{tasks.length}</span></div>{visibleTasks.length ? visibleTasks.map((task) => <div className="task-row" key={task.task_id}><div className={`task-check${task.days_overdue > 0 ? " text-danger" : ""}`}>{task.priority === "high" ? <CircleAlert size={16}/> : <Clock3 size={16}/>}</div><div className="task-copy"><b>{task.title}</b><span>{displayDate(task.due_at)} · {task.days_overdue > 0 ? <span className="pill pill-red">{task.days_overdue} {t("daysOverdue")}</span> : t("today")}</span></div><button className="icon-btn compact" aria-label={t("open")} onClick={() => onTask(task)}><ChevronRight size={16}/></button></div>) : <div className="empty-mini"><Check size={17}/>{t("noPendingTasks")}</div>}<div className="task-bottom"><span><Clock3 size={14}/>{t("overdueLabel")}</span><button className="text-button" onClick={() => onNavigate("households")}>{t("viewAll")} <ChevronRight size={14}/></button></div></section>
  );
  const trendBlock = (
    <section className="panel cockpit-trend"><div className="panel-head"><div><div className="eyebrow">{t("businessTrend")}</div><h2>{t("trendEntry")}</h2></div><button className="text-button" onClick={() => onNavigate("management")}>{t("viewAll")} <ChevronRight size={15}/></button></div><div className="trend-controls"><select aria-label={t("selectMetric")} value={metric} onChange={(event) => setMetric(event.target.value)}>{["inquiries", "visits", "introductions", "contracts", "construction"].map((key) => <option key={key} value={key}>{localeLabel(locale, key)}</option>)}</select><select aria-label={t("period")} value={period} onChange={(event) => setPeriod(event.target.value)}><option value="7d">7d</option><option value="30d">30d</option><option value="90d">90d</option></select></div>
      <TrendResult key={`${data.user.id}:${role}:${metric}:${period}`} metric={metric} period={period} locale={locale} t={t} chart="cockpit"/>
    </section>
  );
  const reportBlock = (
    <>{preferences.dashboard_widgets.includes("report") && <section className="panel cockpit-report"><div className="panel-head"><div><div className="eyebrow">{t("dailySummary")}</div><h2>{t("dailyReport")}</h2></div><FileText size={17} className="muted"/></div><div className="auto-summary"><div className="summary-icon"><Activity size={16}/></div><div><span>{t("autoSummary")}</span><SummaryText summary={data.daily_report?.auto_summary} t={t} locale={locale}/></div></div><label className="field-label">{t("note")}<textarea value={note} onChange={(event) => setNote(event.target.value)} placeholder="..." rows="3"/></label><button className="secondary-btn full-width" onClick={() => onReport(note)}><Check size={15}/>{t("save")}</button></section>}</>
  );
  const overviewBlock = (
    <section className="panel cockpit-overview"><div className="panel-head"><div><div className="eyebrow">{t("businessOverview")}</div><h2>{t("pipeline")}</h2></div><button className="text-button" onClick={() => onNavigate("management")}>{t("viewAll")} <ChevronRight size={15}/></button></div><div className="cockpit-summary-grid"><div><strong>{data.households.length}</strong><span>{t("households")}</span></div><div><strong>{intros}</strong><span>{t("introductions")}</span></div><div><strong>{data.entitlements.length}</strong><span>{t("entitlement")}</span></div></div><small className="muted">{t("currentStageDistribution")}</small><StageFunnel items={data.households} locale={locale}/></section>
  );
  const roleBlocks = role === "executive"
    ? <>{overviewBlock}{tasksBlock}{trendBlock}{reportBlock}</>
    : <>{tasksBlock}{trendBlock}{reportBlock}{overviewBlock}</>;
  return <div className="cockpit-page">{cockpitHeader}{roleBlocks}</div>;
}

function localeLabel(locale, key) {
  const labels = {
    ja: {
      inquiries: "問い合わせ数", visits: "来店相談数", introductions: "紹介数", contracts: "契約数", construction: "着工数",
      "反響": COPY.ja.stage_inquiry, "新規予約": COPY.ja.stage_new_reservation, "初回相談済": COPY.ja.stage_first_consult,
      "訪問予定": COPY.ja.negotiationVisit, "商談中": COPY.ja.negotiationDiscussion, "見積提示": COPY.ja.negotiationEstimate,
      "帰属争議中": COPY.ja.entitlementFrozen,
      "FP診断済": COPY.ja.stage_fp_diagnosis, "紹介済": COPY.ja.stage_introduction,
      "訪問・商談中": COPY.ja.stage_negotiation, "契約": COPY.ja.stage_contract, "着工": COPY.ja.stage_construction, "完了・見送り": COPY.ja.stage_terminal,
    },
    zh: {
      inquiries: "咨询数", visits: "到店咨询数", introductions: "介绍数", contracts: "签约数", construction: "开工数",
      "反響": COPY.zh.stage_inquiry, "新規予約": COPY.zh.stage_new_reservation, "初回相談済": COPY.zh.stage_first_consult,
      "訪問予定": COPY.zh.negotiationVisit, "商談中": COPY.zh.negotiationDiscussion, "見積提示": COPY.zh.negotiationEstimate,
      "帰属争議中": COPY.zh.entitlementFrozen,
      "FP診断済": COPY.zh.stage_fp_diagnosis, "紹介済": COPY.zh.stage_introduction,
      "訪問・商談中": COPY.zh.stage_negotiation, "契約": COPY.zh.stage_contract, "着工": COPY.zh.stage_construction, "完了・見送り": COPY.zh.stage_terminal,
    },
  };
  const localized = labels[locale];
  return localized && Object.hasOwn(localized, key) ? localized[key] : key;
}
function StageFunnel({ items, locale }) {
  const order = ["新規予約", "初回相談済", "FP診断済", "紹介済", "訪問・商談中", "契約", "着工", "完了・見送り"];
  return <div className="funnel-list">{order.slice(0, 6).map((stage, i) => {
    const count = items.filter((h) => h.stage_events.at(-1)?.to_stage === stage).length;
    return <div className="funnel-row" key={stage}><span className="funnel-index">{String(i + 1).padStart(2, "0")}</span><span className="funnel-name">{(locale === "ja" ? stage : localeLabel(locale, stage))}</span>
      <div className="funnel-track"><i style={{ width: `${items.length ? Math.max(4, count / items.length * 100) : 0}%` }}/></div><b>{count}</b></div>;
  })}</div>;
}
function HouseholdTable({ locale, items, t, onOpen, emptyMessage }) {
  const today = todayJst();
  const nextActionFor = (h) => h.activities.find((a) => a.next_action);
  const dueClass = (value) => { if (!value) return ""; const day = String(value).slice(0, 10); return day < today ? "text-danger" : day === today ? "due-today" : ""; };
  const stageFor = (h) => h.stage_events.at(-1)?.to_stage;
  return <><div className="table-scroll household-table-desktop"><table><thead><tr><th>{t("household")}</th><th>{t("stage")}</th><th>{t("nextAction")}</th><th>{t("due")}</th><th/></tr></thead>
    <tbody>{items.map((h) => { const task = nextActionFor(h); return <tr key={h.id} onClick={() => onOpen(h)} className="click-row">
      <td><div className="customer-cell"><div className="customer-avatar">{h.representative_name.slice(0, 1)}</div><div><b>{h.representative_name}</b><span>{h.area_pref}</span></div></div></td>
      <td><span className={stageTagClass(stageFor(h))}>{localeLabel(locale, stageFor(h))}</span></td><td>{task?.next_action || t("nextActionUnset")}</td><td className={dueClass(task?.next_action_due)}>{displayDate(task?.next_action_due)}</td>
      <td><ChevronRight size={15} className="muted"/></td></tr>;})}</tbody></table>{!items.length && <div className="empty-state">{emptyMessage}</div>}</div>
    <div className="household-cards">{items.map((h) => { const task = nextActionFor(h); return <button className="household-record-card" key={h.id} onClick={() => onOpen(h)}>
      <span className="record-card-head"><b>{h.representative_name}</b><span className={stageTagClass(stageFor(h))}>{localeLabel(locale, stageFor(h))}</span></span><span className="record-card-area">{h.area_pref}</span>
      <span className="record-card-action">{task?.next_action || t("nextActionUnset")}</span><span className={`record-card-due ${dueClass(task?.next_action_due)}`}>{displayDate(task?.next_action_due)}</span>
      <span className="record-card-link">{t("viewHousehold")}</span></button>;})}{!items.length && <div className="empty-state">{emptyMessage}</div>}</div></>;
}
function Households({ locale, items, stores, t, onOpen, businessFilter, matchedTasks, terminalExcludedTaskCount, onClearBusinessFilter, searchFeedback }) {
  const [storeId, setStoreId] = useState("all");
  const [stage, setStage] = useState("all");
  const rows = items.filter((household) => (storeId === "all" || household.store_id === Number(storeId))
    && (stage === "all" || household.stage_events.at(-1)?.to_stage === stage));
  const [nameKey, descriptionKey] = businessFilterKeys(businessFilter);
  const taskFilter = isTaskBusinessFilter(businessFilter);
  const scopedHouseholdIds = new Set(rows.map((household) => household.id));
  const scopedTaskCount = matchedTasks.filter((task) => scopedHouseholdIds.has(task.household_id)).length;
  const anyFilter = Boolean(businessFilter) || storeId !== "all" || stage !== "all";
  const emptyMessage = taskFilter && matchedTasks.length === 0 ? t("noMatchingTasks") : anyFilter ? t("noMatchingHouseholds") : t("noHouseholds");
  return <><PageTitle eyebrow={t("customerRelationship")} title={t("households")} sub={t("householdsSub")}/>
    <section className="panel table-panel"><div className="panel-head"><div><h2>{t("households")} <span className="count-badge">{rows.length}</span></h2></div>
      <div className="table-tools"><label className="filter-select">{t("filterStore")}<select value={storeId} onChange={(event) => setStoreId(event.target.value)}>
        <option value="all">{t("allStores")}</option>{stores.map((store) => <option value={store.id} key={store.id}>{store.name}</option>)}</select></label>
        <label className="filter-select">{t("filterStage")}<select value={stage} onChange={(event) => setStage(event.target.value)}>
        <option value="all">{t("all")}</option>{STAGES.map((value) => <option key={value} value={value}>{locale === "zh" ? localeLabel(locale, value) : value}</option>)}</select></label></div></div>
      {businessFilter && <div className="business-filter-banner"><div className="business-filter-copy"><b>{t(nameKey)}</b><span>{t(descriptionKey)}</span>{taskFilter && terminalExcludedTaskCount > 0 && <span className="business-filter-note">{t("businessTerminalExcludedNote").replace("{count}", terminalExcludedTaskCount)}</span>}</div><div className="business-filter-counts"><span><b>{rows.length}</b>{t("targetHouseholds")}</span>{taskFilter && <span><b>{scopedTaskCount}</b>{t("targetTasks")}</span>}</div><button className="business-filter-clear" onClick={onClearBusinessFilter}>{t("clearBusinessFilter")}</button></div>}
      {searchFeedback || <HouseholdTable locale={locale} items={rows} t={t} onOpen={onOpen} emptyMessage={emptyMessage}/>}</section></>;
}
function Introductions({ locale, items, t, onOpen, onAdd, businessFilter, onClearBusinessFilter, focusHouseholdId, onFocusHandled, searchFeedback }) {
  const [activeHousehold, setActiveHousehold] = useState(items[0]?.id || null);
  useEffect(() => { if (!items.some((h) => h.id === activeHousehold)) setActiveHousehold(items[0]?.id || null); }, [items, activeHousehold]);
  useEffect(() => {
    if (focusHouseholdId == null) return;
    if (items.some((h) => h.id === focusHouseholdId)) setActiveHousehold(focusHouseholdId);
    onFocusHandled();
  }, [items, focusHouseholdId, onFocusHandled]);
  const household = items.find((h) => h.id === activeHousehold);
  const filterCopy = businessFilter === "disputed" ? ["introFilterDisputedName", "introFilterDisputedDescription"]
    : businessFilter === "unassigned" ? ["introFilterUnassignedName", "introFilterUnassignedDescription"]
      : businessFilter === "validity:due" ? ["introFilterValidityName", "introFilterValidityDescription"]
        : ["introFilterGenericName", "introFilterGenericDescription"];
  const emptyHouseholds = items.length === 0;
  return <><PageTitle eyebrow={t("partnerJourney")} title={t("introductions")} sub={t("introductionsSub")}/>
    {businessFilter && <div className="business-filter-banner intro-filter-banner"><div className="business-filter-copy"><b>{t(filterCopy[0])}</b><span>{t(filterCopy[1])}</span></div><div className="business-filter-counts"><span><b>{items.length}</b>{t("targetHouseholds")}</span></div><button className="business-filter-clear" onClick={onClearBusinessFilter}>{t("clearBusinessFilter")}</button></div>}
    <div className="intro-layout"><section className="panel intro-list"><div className="panel-head"><h2>{t("households")}</h2><span className="count-badge">{items.length}</span></div>
      {searchFeedback || (emptyHouseholds ? <div className="empty-mini">{t(businessFilter ? "noMatchingHouseholds" : "noHouseholds")}</div>
        : <div className="intro-household-list" role="group" aria-label={t("households")}>{items.map((h) =>
          <button type="button" className={`intro-household ${activeHousehold === h.id ? "selected" : ""}`}
            aria-pressed={activeHousehold === h.id} key={h.id} onClick={() => setActiveHousehold(h.id)}>
            <div className="customer-avatar">{h.representative_name.slice(0, 1)}</div>
            <div><b>{h.representative_name}</b><span>{h.area_pref}</span></div>
            <span className="intro-count">{h.introductions.length}</span>
          </button>)}</div>)}</section>
      {household ? <section className="intro-detail"><div className="panel intro-context"><div><div className="eyebrow">{household.store_name} · {household.advisor_name}</div><h2>{household.representative_name}</h2><span>{household.budget_band} · {household.area_pref}</span></div>
        <button className="primary-btn" onClick={() => onAdd(household)}><Plus size={15}/>{t("partnerCreate")}</button></div>
        <div className="partner-grid">{!household.introductions.length && <div className="empty-state intro-empty-partners">{t("introNoIntroductions")}</div>}{household.introductions.map((intro) => <PartnerCard locale={locale} key={intro.id} intro={intro} t={t} onOpen={() => onOpen(household)}/>)}
          {!household.introductions.length && <button className="add-partner-card" onClick={() => onAdd(household)}><Plus size={20}/>{t("partnerCreate")}</button>}</div>
      </section> : !searchFeedback && <section className="panel empty-state">{t("introSelectHousehold")}</section>}
    </div></>;
}
function PartnerCard({ locale, intro, t, onOpen }) {
  const elapsed = Math.max(0, Math.floor((Date.now() - new Date(intro.introduced_at).getTime()) / 86400000));
  const state = intro.entitlement_state;
  return <article className={`partner-card ${state === "Disputed" ? "disputed-card" : ""}`}>
    <div className="partner-card-head"><div className="partner-icon"><Building2 size={18}/></div><div><b>{intro.partner_name}</b><span>{intro.staff_name || "—"} · {displayDate(intro.introduced_at)}</span></div>
      {intro.existing_customer_flag ? <CustomerDisputeBadge t={t}/> : <span className={`pill ${intro.status === "受付確認済" ? "pill-blue" : "pill-violet"}`}>{t(intro.status === "受付確認済" ? "received" : "introduced")}</span>}</div>
    <div className="negotiation-status"><div><small>{t("status")}</small><b>{localeLabel(locale, intro.negotiation_status || "紹介済")}</b></div><div><small>{t("elapsed")}</small><b>{elapsed} {t("days")}</b></div><div><small>{t("last")}</small><b>{displayDate(intro.last_activity_at)}</b></div></div>
    {intro.contract_id && <div className="contract-highlight"><div className="contract-icon"><Check size={15}/></div><div><b>{t("contract")} · ¥{Number(intro.contract_amount).toLocaleString()}</b><span>{displayDate(intro.contract_date)}</span></div></div>}
    {state === "Disputed" && <div className="frozen-banner"><CircleAlert size={15}/><span>{t("entitlementFrozen")} · {t("frozen")}</span></div>}
    <button className="card-link" onClick={onOpen}>{t("review")} <ChevronRight size={14}/></button>
  </article>;
}
function Revenue({ data, t, role, api, onOpen, filter, onClearBusinessFilter }) {
  const projectItems = data.households.flatMap((household) => household.introductions
    .filter((intro) => intro.project_id && !intro.confirmed_start_date)
    .map((intro) => ({ household, project: intro })));
  const queue = filter.startsWith("construction:") && filter !== "construction:pending"
    ? projectItems.filter(({ project }) => project.confirmation_status === filter.slice("construction:".length))
    : projectItems;
  const filteredEntitlements = data.entitlements.filter((e) => filter !== "disputed" || e.state === "Disputed").filter((e) => !filter.startsWith("entitlements:") || (filter === "entitlements:Pending" ? e.state === "Pending" : filter === "entitlements:Invoiced" ? e.state === "Invoiced" : filter === "entitlements:invoice_data_pending" ? e.state === "Confirmed" && !e.invoice_data_generated : true));
  const disputes = data.entitlements.filter((item) => item.state === "Disputed");
  const sumState = (states) => data.entitlements.filter((item) => states.includes(item.state))
    .reduce((sum, item) => sum + Number(item.calculated_amount || 0), 0);
  const plannedAmount = projectItems.reduce((sum, item) => sum + Math.round(Number(item.contract_amount || 0) * 0.02), 0);
  const overdueProjects = Number(data.construction_confirmation_backlog || 0);
  const freezeAmount = disputes.reduce((sum, item) => sum + Number(item.calculated_amount || 0), 0);
  const referenceAmount = disputes.reduce((sum, item) => sum + Number(item.reference_amount || 0), 0);
  const feeRuleParams = (value) => typeof value === "string" ? JSON.parse(value) : value;
  let nameKey, descKey, areaKey, N;
  if (filter === "construction:pending") { nameKey = "revFilterConstructionPendingName"; descKey = "revFilterConstructionPendingDesc"; areaKey = "revFilterAreaQueue"; N = queue.length; }
  else if (filter.startsWith("construction:")) { nameKey = "revFilterConstructionName"; descKey = "revFilterConstructionDesc"; areaKey = "revFilterAreaQueue"; N = queue.length; }
  else if (filter === "entitlements:Pending") { nameKey = "revFilterEntPendingName"; descKey = "revFilterEntPendingDesc"; areaKey = "revFilterAreaLedger"; N = filteredEntitlements.length; }
  else if (filter === "entitlements:Invoiced") { nameKey = "revFilterEntInvoicedName"; descKey = "revFilterEntInvoicedDesc"; areaKey = "revFilterAreaLedger"; N = filteredEntitlements.length; }
  else if (filter === "entitlements:invoice_data_pending") { nameKey = "revFilterEntInvoiceDataPendingName"; descKey = "revFilterEntInvoiceDataPendingDesc"; areaKey = "revFilterAreaLedger"; N = filteredEntitlements.length; }
  else if (filter === "disputed") { nameKey = "revFilterDisputedName"; descKey = "revFilterDisputedDesc"; areaKey = "revFilterAreaLedger"; N = filteredEntitlements.length; }
  const banner = nameKey !== undefined;
  return <><PageTitle eyebrow={t("constructionRevenue")} title={t("revenue")} sub={t("revenueSub")}/>{banner && <div className="business-filter-banner"><div className="business-filter-copy"><b>{t(nameKey)}</b><span>{t(descKey)}</span></div><div className="business-filter-counts"><span>{t(areaKey)}</span><span><b>{N}</b>{t("revFilterUnit")}</span></div><button className="business-filter-clear" onClick={onClearBusinessFilter}>{t("clearBusinessFilter")}</button></div>}
    <p className="revenue-metrics-note">{t("revMetricsNote")}</p>
    <div className="revenue-metrics"><Metric small label={t("plannedFee")} value={`¥${plannedAmount.toLocaleString()}`} icon={CalendarDays} tone="neutral"/>
      <Metric small label={t("feeReview")} value={`¥${sumState(["Pending"]).toLocaleString()}`} icon={Clock3} tone="amber"/>
      <Metric small label={t("approvedFee")} value={`¥${sumState(["Confirmed"]).toLocaleString()}`} icon={BadgeJapaneseYen} tone="blue"/>
      <Metric small label={t("invoiceAmount")} value={`¥${sumState(["Invoiced"]).toLocaleString()}`} icon={FileText} tone="violet"/>
      <Metric small label={t("paidAmount")} value={`¥${sumState(["Paid"]).toLocaleString()}`} icon={WalletCards} tone="green"/>
      <Metric small label={t("confirmedRevenue")} value={`¥${sumState(["Confirmed", "Invoiced", "Paid"]).toLocaleString()}`} icon={BadgeJapaneseYen} tone="emphasis"/></div>
    <section className="panel construction-queue-panel"><div className="panel-head"><div><div className="eyebrow">{t("constructionConfirmation")}</div><h2>{t("confirmStart")} · {queue.length}</h2></div>
      <span className="pill pill-orange">{t("overdueLabel")} {overdueProjects}</span></div>
      <div className="construction-queue">{queue.map(({ household, project }) => <ConstructionCard key={project.project_id}
        household={household} project={project} t={t} role={role} api={api}/>)}
      {!queue.length && <div className="empty-state">{t(filter.startsWith("construction:") ? "revNoMatchingProjects" : "noRows")}</div>}</div>
    </section>
    <section className="panel entitlement-panel"><div className="panel-head"><div><div className="eyebrow">{t("revenueLedger")}</div><h2>{t("entitlement")}</h2></div>
      <span className="pill pill-green">{t("appendOnlyAudit")}</span></div>
      <div className="table-scroll"><table><thead><tr><th>{t("household")}</th><th>{t("partner")}</th><th>{t("basis")}</th><th>{t("rule")}</th><th>{t("amount")}</th><th>{t("status")}</th><th/></tr></thead><tbody>
      {filteredEntitlements.map((e) => <tr key={e.id}><td data-label={t("household")}><b>{e.representative_name}</b></td><td data-label={t("partner")}>{e.partner_name}</td>
        <td data-label={t("basis")}>¥{Number(e.base_amount).toLocaleString()} × {feeRuleParams(e.params).rate ? `${feeRuleParams(e.params).rate * 100}%` : "—"}</td>
        <td data-label={t("rule")}><span className="rule-chip">v{e.rule_version}</span> {e.base}</td><td data-label={t("amount")} className="amount-cell">¥{Number(e.calculated_amount).toLocaleString()}</td>
        <td data-label={t("status")}><StateBadge state={e.state} t={t}/></td><td data-label=""><EntitlementActions entitlement={e} t={t} role={role} api={api}/></td></tr>)}</tbody></table>
        {!data.entitlements.length && <div className="empty-state">{t("noEntitlement")}</div>}{data.entitlements.length > 0 && !filteredEntitlements.length && (filter.startsWith("entitlements:") || filter === "disputed") && <div className="empty-state">{t("revNoMatchingRecords")}</div>}</div></section>
    {disputes.length > 0 ? <section className="panel dispute-note"><CircleAlert size={18}/><div><b>{t("disputed")} {disputes.length} · {t("frozen")}</b>
      <span>{t("referenceAmount")}: ¥{referenceAmount.toLocaleString()} · {t("frozenAmount")}: ¥{freezeAmount.toLocaleString()} · {t("accountingNote")}</span></div></section> : <section className="panel dispute-note dispute-note-neutral"><CircleAlert size={18}/><div><b>{t("revNoDisputes")}</b></div></section>}
    {disputes.map((item) => <DisputeResolution key={item.id} item={item} t={t} role={role} api={api}/>)}
  </>;
}
function ConstructionCard({ household, project, data, t, role, api }) {
  const [evidence, setEvidence] = useState(project.confirmation_evidence || "");
  const canConfirm = role === "manager" || role === "hq_finance" || role === "executive";
  const stateLabel = t(`construction_${project.confirmation_status}`);
  return <section className="panel construction-panel"><div className="panel-head"><div><div className="eyebrow">{t("projectMilestone")}</div><h2>{household.representative_name} · {project.partner_name}</h2>
    <small>{stateLabel} · {t("due")}: {displayDate(project.confirmation_due_date)}</small></div><StateBadge state={project.confirmed_start_date ? "Confirmed" : "PendingConfirmation"} t={t}/></div>
    <div className="milestone-line"><div className="milestone done"><div><Check size={15}/></div><span>{t("contract")}</span><b>{displayDate(project.contract_date)}</b></div><div className="milestone done"><div><Check size={15}/></div><span>{t("startPlanned")}</span><b>{displayDate(project.planned_start_date)}</b></div>
      <div className="milestone done"><div><Check size={15}/></div><span>{t("actualStart")}</span><b>{displayDate(project.actual_start_date)}</b></div><div className={`milestone ${project.confirmed_start_date ? "done" : "pending"}`}><div>{project.confirmed_start_date ? <Check size={15}/> : "4"}</div><span>{t("confirmStart")}</span><b>{displayDate(project.confirmed_start_date)}</b></div></div>
    {!project.confirmed_start_date && canConfirm ? <div className="confirm-row"><label className="field-label">{t("confirmationEvidence")}<input value={evidence} onChange={(e) => setEvidence(e.target.value)} placeholder="現場写真・担当者確認など"/></label>
      <button className="primary-btn" disabled={!evidence.trim() || !project.actual_start_date} onClick={() => api(`/api/construction/${project.project_id}/confirm`, "POST", { confirmed_start_date: todayJst(), evidence })}><Check size={15}/>{t("confirm")}</button></div>
      : !project.confirmed_start_date ? <div className="inline-notice"><ShieldCheck size={16}/>{t("roleFinance")} または {t("roleManager")} ロールで着工確認ができます。</div>
      : <div className="success-notice"><Check size={16}/>{t("confirmed")} · {project.confirmation_evidence}</div>}
    {project.entitlement_id && <div className="generated-fee"><div className="metric-icon green"><BadgeJapaneseYen size={18}/></div><div><span>{t("entitlement")} · {t("basis")}</span><b>¥{Number(project.contract_amount).toLocaleString()} × {feeRate(project.rule_params)} = ¥{Number(project.calculated_amount).toLocaleString()}</b></div><span className="rule-chip">FeeRule v{project.rule_version}</span></div>}
  </section>;
}
function feeRate(params) {
  const parsed = typeof params === "string" ? JSON.parse(params) : params;
  return parsed?.rate ? `${parsed.rate * 100}%` : "—";
}
function DisputeResolution({ item, t, role, api }) {
  const [note, setNote] = useState("");
  const [decision, setDecision] = useState("confirm");
  return <section className="panel dispute-resolution"><div><b>{t(`disputeType_${item.dispute_type}`)} · {item.representative_name}</b>
    <span>{t("evidence")}: {item.evidence_level} · {t("referenceAmount")}: ¥{Number(item.reference_amount).toLocaleString()} · {item.dispute_status}</span></div>
    {role === "hq_finance" ? <div className="dispute-actions"><select value={decision} onChange={(event) => setDecision(event.target.value)}>
      <option value="confirm">{t("approve")}</option><option value="reassessment">{t("reassessment")}</option>
      <option value="write_off">{t("writeOff")}</option></select>
      <input value={note} onChange={(event) => setNote(event.target.value)} placeholder={t("decisionReason")}/>
      <button className="mini-action" disabled={!item.dispute_id || note.trim().length < 5}
        onClick={() => api(`/api/referral-disputes/${item.dispute_id}/decision`, "POST", { decision, decision_note: note })}>{t("resolveDispute")}</button>
    </div> : <StateBadge state="Disputed" t={t}/>}
  </section>;
}
const ENTITLEMENT_STATE_KEYS = {
  Confirmed: "stateConfirmed", Invoiced: "stateInvoiced", Paid: "statePaid", Disputed: "stateDisputed",
  PendingConfirmation: "statePendingConfirmation", Estimated: "stateEstimated", Potential: "statePotential",
  WrittenOff: "stateWrittenOff", Pending: "statePending",
};

function entitlementStateLabel(state, t) {
  return t && Object.hasOwn(ENTITLEMENT_STATE_KEYS, state) ? t(ENTITLEMENT_STATE_KEYS[state]) : state;
}

function StateBadge({ state, t }) {
  return <span className={`state-badge state-${state?.toLowerCase()}`}>{state === "Disputed" && <CircleAlert size={13}/>} {entitlementStateLabel(state, t)}</span>;
}
function EntitlementActions({ entitlement, t, role, api }) {
  if (entitlement.state === "Disputed") return <span className="frozen-label"><CircleAlert size={13}/>{t("frozen")}</span>;
  if (role !== "hq_finance") return <span className="muted">—</span>;
  if (entitlement.state === "Pending") return <button className="mini-action" onClick={() => api(`/api/entitlements/${entitlement.id}/action`, "POST", { action: "approve" })}>{t("approve")} <ChevronRight size={13}/></button>;
  if (entitlement.state === "Confirmed") return <button className="mini-action" onClick={() => api(`/api/entitlements/${entitlement.id}/action`, "POST", { action: "invoice" })}>{t("invoice")} <ChevronRight size={13}/></button>;
  if (entitlement.state === "Invoiced") return <button className="mini-action" onClick={() => api(`/api/entitlements/${entitlement.id}/action`, "POST", { action: "paid" })}>{t("paid")} <ChevronRight size={13}/></button>;
  return <span className="muted">—</span>;
}
function getTrendState(result) {
  const isCount = (value) => Number.isSafeInteger(value) && value >= 0;
  if (!Array.isArray(result?.current) || !isCount(result.current_total)
      || !isCount(result.previous_total) || result.current.some((point) => !isCount(point?.value))) {
    return "invalid";
  }
  if (result.current.some((point) => point.value > 0)) return "positive";
  if (result.current_total !== 0) return "invalid";
  return result.current.length === 0 ? "empty" : "zero";
}

function TrendResult({ metric, period, locale, t, chart }) {
  const [result, setResult] = useState({ state: "loading" });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    fetch(`${API_BASE}/api/dashboard/trends?metric=${metric}&period=${period}`, {
      credentials: "include", signal: controller.signal,
    }).then(async (response) => {
      if (!response.ok) throw new Error("Trend request failed");
      const data = await response.json();
      if (!controller.signal.aborted) setResult({ state: getTrendState(data), data });
    }).catch(() => {
      if (!controller.signal.aborted) setResult({ state: "error" });
    });
    return () => controller.abort();
  }, [metric, period, attempt]);

  const periodLabel = t("trendRecentDays")(period.slice(0, -1));
  const { state, data } = result;
  if (state === "loading") return <>
    <p className="trend-period">{periodLabel}</p>
    <div className="trend-feedback" role="status"><span className="spinner" aria-hidden="true"/>{t("trendLoading")}</div>
  </>;
  if (state === "error" || state === "invalid") return <>
    <p className="trend-period">{periodLabel}</p>
    <div className="trend-feedback config-error" role="alert">
      <span>{t(state === "error" ? "trendLoadFailed" : "trendInvalid")}</span>
      <button type="button" className="secondary-btn" onClick={() => {
        setResult({ state: "loading" });
        setAttempt((value) => value + 1);
      }}>{t("searchRetry")}</button>
    </div>
  </>;

  const cockpit = chart === "cockpit";
  const management = chart === "management";
  const summary = <div className={cockpit ? "cockpit-trend-summary" : "trend-summary"}>
    <strong>{data.current_total}</strong>
    <span>{periodLabel} · {management ? `${t("previousPeriod")} ${data.previous_total}` : localeLabel(locale, metric)}</span>
  </div>;
  const showBars = chart && state === "positive";
  const max = showBars ? Math.max(...data.current.map((point) => point.value)) : 0;
  return <>
    {!management && summary}
    {showBars && <div className={cockpit ? "cockpit-trend-bars" : "trend-bars"}>
      {data.current.map((point, index) => {
        const date = point.date || point.start;
        return <div key={`${date}-${index}`} title={`${displayDate(date)}: ${point.value}`}>
          {point.value > 0 && <i style={{ height: `${Math.max(cockpit ? 8 : 3, point.value / max * 100)}%` }}/>}
        </div>;
      })}
    </div>}
    {management && summary}
    {state === "empty" && <div className="empty-state">{t("trendEmpty")}</div>}
    {state === "zero" && <div className="empty-state">{t("trendZero")}</div>}
  </>;
}

function exceptionTitle(cardKey, title, locale, t) {
  if (cardKey === "construction_confirmation") return COPY[locale][`construction_${title}`] || title;
  if (cardKey === "open_disputes") return COPY[locale][`disputeType_${title}`] || title;
  if (cardKey === "invoice_unpaid") return entitlementStateLabel(title, t);
  return title;
}

const AUDIT_ACTION_LABELS = {
  "management.report_generated": ["経営レポートを生成", "生成经营报告"],
  "demo.login.disabled": ["無効なデモログイン", "演示登录已禁用"],
  "auth.login": ["ログイン", "登录"],
  "auth.logout": ["ログアウト", "退出登录"],
  "auth.password_changed": ["パスワードを変更", "修改密码"],
  PASSWORD_RESET_REQUESTED: ["パスワード再設定を申請", "申请重置密码"],
  PASSWORD_RESET: ["パスワードを再設定", "重置密码"],
  DEMO_DATA_RESET: ["デモデータを初期化", "重置演示数据"],
  "account.handoff": ["アカウント業務を引継ぎ", "交接账号业务"],
  "account.status_changed": ["アカウント状態を変更", "更改账号状态"],
  "account.role_transferred": ["アカウント権限を移管", "移交账号权限"],
  "activity.created": ["活動を登録", "记录活动"],
  "calendar_event.created": ["予定を登録", "新增日程"],
  "calendar_event.updated": ["予定を更新", "更新日程"],
  "negotiation.next_action.updated": ["商談の次の対応を更新", "更新洽谈下一步"],
  "bulletin.daily_report.updated": ["掲示板の日報を更新", "更新公告栏日报"],
  "bulletin.daily_report.published": ["掲示板に日報を公開", "发布日报到公告栏"],
  "bulletin.post.created": ["掲示板に投稿", "发布公告"],
  "bulletin.post.updated": ["掲示板の投稿を更新", "更新公告"],
  "bulletin.post.archived": ["掲示板の投稿を保管", "归档公告"],
  "bulletin.comment.created": ["コメントを投稿", "发布评论"],
  "introduction.created": ["紹介を登録", "登记介绍"],
  "referral_consent.granted": ["紹介同意を登録", "记录介绍授权"],
  "referral_consent.revoked": ["紹介同意を撤回", "撤回介绍授权"],
  "referral_document.generated": ["紹介文書を生成", "生成介绍文档"],
  "referral_document.generation_failed": ["紹介文書の生成に失敗", "介绍文档生成失败"],
  "referral_document.previewed": ["紹介文書をプレビュー", "预览介绍文档"],
  "referral_document.downloaded": ["紹介文書をダウンロード", "下载介绍文档"],
  "referral_document.access_denied": ["紹介文書へのアクセスを拒否", "拒绝访问介绍文档"],
  "referral_document.integrity_failed": ["紹介文書の整合性確認に失敗", "介绍文档完整性检查失败"],
  "referral_document.file_expired": ["紹介文書の保存期限が満了", "介绍文档保留期届满"],
  "construction.confirmed": ["着工を確認", "确认开工"],
  "entitlement.approve": ["報酬を承認", "批准报酬"],
  "entitlement.invoice": ["請求データを生成", "生成请款数据"],
  "entitlement.paid": ["入金を記録", "记录入金"],
  "referral_dispute.raised": ["紹介争議を申請", "提出介绍争议"],
  "referral_dispute.decided": ["紹介争議を裁定", "裁决介绍争议"],
  "data_disclosure.created": ["情報開示を登録", "登记信息披露"],
  "data_correction.requested": ["データ訂正を申請", "申请数据修正"],
  "data_correction.approved": ["データ訂正を承認", "批准数据修正"],
  "data_correction.rejected": ["データ訂正を却下", "驳回数据修正"],
  "stage.changed": ["進捗段階を変更", "更改进度阶段"],
  "system_config.updated": ["システム設定を更新", "更新系统设置"],
  "daily_report.saved": ["日報を保存", "保存日报"],
  "expense.created": ["経費を登録", "登记费用"],
  "expense.updated": ["経費を更新", "更新费用"],
  "expense.receipt_uploaded": ["領収書を添付", "附加收据"],
  "expense.submitted": ["経費を申請", "提交费用申请"],
  "expense.approved": ["経費を承認", "批准费用"],
  "expense.rejected": ["経費を差し戻し", "退回费用"],
  "expense.recorded": ["経費を帳簿に記録", "费用入账"],
  "export.created": ["エクスポートを作成", "创建导出文件"],
  "export.integrity_failed": ["エクスポートの整合性確認に失敗", "导出文件完整性检查失败"],
  "export.downloaded.csv": ["CSVをダウンロード", "下载 CSV"],
  "export.downloaded.pdf": ["PDFをダウンロード", "下载 PDF"],
  "month_close.prepared": ["月次締めを準備", "准备月度结账"],
  "month_close.closed": ["月次締めを確定", "确认月度结账"],
  "month_close.reopen_requested": ["月次締めの再開を申請", "申请重开月度结账"],
  "month_close.reopened": ["月次締めを再開", "重开月度结账"],
  "kintone.import_previewed": ["kintone取込をプレビュー", "预览 kintone 导入"],
  "kintone.import_completed": ["kintone取込を完了", "完成 kintone 导入"],
};

function AuditOperation({ action, locale, t }) {
  const label = action === "DEMO_ROLE_SWITCH" ? t("auditDemoRoleSwitch")
    : Object.hasOwn(AUDIT_ACTION_LABELS, action) ? AUDIT_ACTION_LABELS[action][locale === "zh" ? 1 : 0] : null;
  if (!label) return <span className="audit-action">{action}</span>;
  return <details className="audit-operation">
    <summary title={action}>{label}</summary>
    <code>{action}</code>
  </details>;
}

function Management({ locale, data, t, role, onReminder, onException }) {
  const [metric, setMetric] = useState("introductions");
  const [period, setPeriod] = useState("90d");
  const [focusedReminder, setFocusedReminder] = useState(null);
  const [reportBusy, setReportBusy] = useState(false);
  const [reportError, setReportError] = useState("");
  const [overview, setOverview] = useState({ state: "loading" });
  const [overviewAttempt, setOverviewAttempt] = useState(0);
  const canLoadOverview = ["manager", "hq_finance", "executive"].includes(role);
  useEffect(() => {
    if (!canLoadOverview) return;
    const controller = new AbortController();
    fetch(`${API_BASE}/api/management/overview`, { credentials: "include", signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error("Management request failed");
        const data = await response.json();
        if (!controller.signal.aborted) setOverview({ state: "success", data });
      }).catch(() => {
        if (!controller.signal.aborted) setOverview({ state: "error" });
      });
    return () => controller.abort();
  }, [canLoadOverview, overviewAttempt]);
  const management = overview.data;
  const stores = management?.stores || [];
  const funnel = management?.funnel || [];
  const max = Math.max(...stores.map((item) => item.households || 0), 1);
  const dimensionLabels = [
    ["followup_rate", t("followupRate")], ["data_completeness", t("completeness")],
    ["next_action_rate", t("nextActionRate")], ["report_submission_rate", t("reportRate")],
    ["response_rate", t("responseQuality")],
  ];
  async function openReport(reportType) {
    const preview = window.open("about:blank", "_blank");
    setReportBusy(true);
    setReportError("");
    try {
      const response = await fetch(`${API_BASE}/api/management/reports`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ report_type: reportType }),
      });
      if (!response.ok) throw new Error(t("reportFailed"));
      const reportUrl = URL.createObjectURL(await response.blob());
      if (preview) preview.location.href = reportUrl;
      else {
        const link = document.createElement("a");
        link.href = reportUrl;
        link.download = `sumaiboard_${reportType}.pdf`;
        link.click();
      }
      setTimeout(() => URL.revokeObjectURL(reportUrl), 60000);
    } catch {
      preview?.close();
      setReportError(t("reportFailed"));
    } finally { setReportBusy(false); }
  }
  return <div className="admin-page management-page"><PageTitle eyebrow={t("businessIntelligence")} title={t("management")} sub={t("managementSub")}/>
    {canLoadOverview && overview.state === "loading" && <div className="workspace-load" role="status">
      <span className="spinner" aria-hidden="true"/>{t("loadingRecords")}
    </div>}
    {canLoadOverview && overview.state === "error" && <div className="workspace-load config-error" role="alert">
      <span>{t("managementLoadFailed")}</span>
      <button type="button" className="secondary-btn" onClick={() => {
        setOverview({ state: "loading" });
        setOverviewAttempt((value) => value + 1);
      }}>{t("searchRetry")}</button>
    </div>}
    <div className="management-grid management-primary"><section className="panel analytics-panel"><div className="panel-head"><div><div className="eyebrow">{t("storeComparison")}</div><h2>{t("storeCompare")}</h2></div></div>
      <div className="store-bars">{stores.map((store) => <div className="store-bar-row store-comparison-row" key={store.id}>
        <span>{store.name}</span><div className="bar-track"><i style={{ width: `${store.households / max * 100}%` }}/></div>
        <b>{store.households}</b><small>{store.tenure_months}{t("months")} · {store.case_volume_band} {t("caseVolume")}</small>
      </div>)}</div><div className="chart-footnote">{t("sampleSize")} · {t("households")} · {t("demoWarning")}</div></section>
      <section className="panel analytics-panel"><div className="panel-head"><div><div className="eyebrow">{t("businessTrend")}</div><h2>{t("trendEntry")}</h2></div></div>
        <div className="trend-controls"><select aria-label={t("selectMetric")} value={metric} onChange={(event) => setMetric(event.target.value)}>
          {["inquiries", "visits", "introductions", "contracts", "construction"].map((key) => <option value={key} key={key}>{localeLabel(locale, key)}</option>)}
        </select><select aria-label={t("period")} value={period} onChange={(event) => setPeriod(event.target.value)}>
          {["7d", "30d", "90d", "180d", "365d"].map((value) => <option key={value}>{value}</option>)}
        </select></div>
        <TrendResult key={`${data.user.id}:${role}:${metric}:${period}`} metric={metric} period={period} locale={locale} t={t} chart="management"/>
      </section></div>
    {funnel.length > 0 && <section className="panel management-funnel"><div className="panel-head"><div>
      <div className="eyebrow">{t("last90Days")}</div><h2>{t("acquisitionFunnel")}</h2></div>
      <span className="muted">{t("funnelReference")}</span></div>
      <div className="management-funnel-list">{funnel.map((item, index) => <div className="management-funnel-row" key={item.stage}>
        <span>{String(index + 1).padStart(2, "0")} · {localeLabel(locale, item.stage)}</span>
        <div className="funnel-track"><i style={{ width: `${Math.min(100, item.count / Math.max(...funnel.map((entry) => entry.count), 1) * 100)}%` }}/></div>
        <b>{item.count}</b>
      </div>)}</div>
    </section>}
    {management?.exception_cards?.length > 0 && <section className="panel exception-panel">
      <div className="panel-head"><div><div className="eyebrow">{t("exceptionCards")}</div><h2>{t("actionRequired")}</h2></div></div>
      <div className="exception-card-grid">{management.exception_cards.map((card) => <article className="exception-card" key={card.key}>
        <h3>{t(`exception_${card.key}`)}<strong>{card.count}</strong></h3>
        {card.items.map((item) => <button key={`${card.key}-${item.record_id}`}
          onClick={() => onException(card, item)}>
          <span>{item.representative_name}</span>
          <small>{exceptionTitle(card.key, item.title, locale, t) || (item.due_at ? displayDate(item.due_at) : t("exceptionOpenRecord"))}</small>
          <ChevronRight size={13}/>
        </button>)}
        {!card.items.length && <p className="muted">{t("noRows")}</p>}
      </article>)}</div>
    </section>}
    {management && <section className="panel special-reports-panel">
      <div className="panel-head"><div><div className="eyebrow">{t("specialReports")}</div><h2>{t("openPdfReport")}</h2></div></div>
      {reportError && <p className="config-error" role="alert">{reportError}</p>}
      <div className="special-report-actions">
        {[["operations", "reportOperations"], ["funnel", "reportFunnel"],
          ["attribution", "reportAttribution"], ["partner_quality", "reportPartnerQuality"]]
          .map(([reportType, label]) => <button className="secondary-btn" key={reportType}
            disabled={reportBusy} onClick={() => openReport(reportType)}>
            <FileText size={14}/>{t(label)}
          </button>)}
      </div>
    </section>}
    {management?.operations_dimensions?.length > 0 && <section className="panel operations-panel"><div className="panel-head"><div><div className="eyebrow">{t("storeOperations")}</div><h2>{t("operationsStatus")}</h2></div><span className="pill pill-blue">{t("noScore")}</span></div>
      <div className="table-scroll"><table><thead><tr><th>{t("stores")}</th>{dimensionLabels.map(([,label]) => <th key={label}>{label}</th>)}<th>{t("sampleSize")}</th></tr></thead>
        <tbody>{management.operations_dimensions.map((row) => <tr key={row.store_id}><td>{stores.find((store) => store.id === row.store_id)?.name}</td>
          {dimensionLabels.map(([key]) => <td key={key}>{Math.round((row[key] || 0) * 100)}%</td>)}<td>{row.sample_size}</td></tr>)}</tbody></table></div>
    </section>}
    {management && <><section className="panel reminders-panel"><div className="panel-head"><div><div className="eyebrow">{t("deadlineReminders")}</div><h2>{t("reminders")}</h2></div></div>
      <div className="reminder-grid">{management.reminders.map((reminder) => <article className="reminder-card" key={reminder.key}>
        <h3>{t(`reminder_${reminder.key}`)}<span>{reminder.items.length}</span></h3>
        {reminder.items.map((item) => <button key={`${reminder.key}-${item.id}`} onClick={() => {
          setFocusedReminder({ key: reminder.key, item });
          onReminder(reminder, item);
        }}>
          <span>{item.representative_name}</span><small>{displayDate(item.due_at)}</small><ChevronRight size={14}/></button>)}
        {!reminder.items.length && <p className="muted">{t("noRows")}</p>}
      </article>)}</div>
      {focusedReminder && <div className="inline-notice" aria-live="polite">
        <b>{t("selectedDeadline")} · {t(`reminder_${focusedReminder.key}`)}</b>
        <span>{t("deadlineRecord")}: {focusedReminder.item.representative_name} · {displayDate(focusedReminder.item.due_at)} · #{focusedReminder.item.id}</span>
      </div>}
    </section>
    <div className="management-grid"><section className="panel analytics-panel"><div className="panel-head"><div><div className="eyebrow">{t("marketingAttribution")}</div><h2>{t("attribution")}</h2></div></div>
      <div className="table-scroll"><table><thead><tr><th>{t("firstTouch")}</th><th>{t("touch")}</th><th>{t("households")}</th><th>{t("contract")}</th></tr></thead>
        <tbody>{management.attribution.map((row) => <tr key={row.channel}><td>{row.channel}</td><td>{row.touches}</td><td>{row.households}</td><td>{row.contracts}</td></tr>)}</tbody></table></div>
    </section><section className="panel analytics-panel"><div className="panel-head"><div><div className="eyebrow">{t("cohortConversion")}</div><h2>{t("cohort")}</h2></div>
      <span className="muted">{t("cohortReference")}</span></div>
      <div className="table-scroll"><table><thead><tr><th>{t("cohort")}</th><th>{t("inquiryToReservation")}</th><th>{t("reservationToIntroduction")}</th><th>{t("introductionToContract")}</th></tr></thead>
        <tbody>{management.cohorts.map((row) => {
          const rateLabel = (value) => value?.rate == null ? "—" : `${(value.rate * 100).toFixed(1)}% (${value.numerator}/${value.denominator})`;
          return <tr key={row.cohort}><td>{displayDate(row.cohort)}</td><td>{rateLabel(row.inquiry_to_reservation)}</td>
            <td>{rateLabel(row.reservation_to_introduction)}</td><td>{rateLabel(row.introduction_to_contract)}</td></tr>;
        })}</tbody></table></div>
    </section></div>
    <section className="panel analytics-panel"><div className="panel-head"><div><div className="eyebrow">{t("partnerSettlementQuality")}</div><h2>{t("partnerQuality")}</h2></div></div>
      <div className="table-scroll"><table><thead><tr><th>{t("partner")}</th><th>{t("introductions")}</th><th>{t("disputed")}</th><th>{t("paid")}</th><th>{t("amount")}</th></tr></thead>
        <tbody>{management.partner_quality.map((row) => <tr key={row.id}><td>{row.name}</td><td>{row.introductions}</td><td>{row.disputes}</td>
          <td>{row.paid}</td><td>¥{Number(row.paid_amount).toLocaleString()}</td></tr>)}</tbody></table></div>
    </section></>}
    <section className="panel governance-panel"><div className="panel-head"><div><div className="eyebrow">{t("governance")}</div><h2>{t("audit")}</h2></div><span className="pill pill-green"><ShieldCheck size={13}/>{t("audit")}</span></div>
      <div className="table-scroll"><table><thead><tr><th>{t("dateLabel")}</th><th>{t("userLabel")}</th><th>{t("actionLabel")}</th><th>{t("targetLabel")}</th><th>{t("detailLabel")}</th></tr></thead><tbody>
        {data.audit_logs.map((row) => <tr key={row.id}><td>{displayDate(row.at)}</td><td>{row.user_name || "—"}</td><td><AuditOperation action={row.action} locale={locale} t={t}/></td><td>{row.target_type} #{row.target_id}</td><td>{row.detail}</td></tr>)}
      </tbody></table>{!data.audit_logs.length && <div className="empty-state">{t("noRows")}</div>}</div></section>
  </div>;
}
function AuditTrailPanel({ t, userId, locale }) {
  const [items, setItems] = useState([]);
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState("");
  const activeRequest = useRef(0);
  useEffect(() => {
    const requestId = ++activeRequest.current;
    setItems([]);
    setSelected(null);
    fetch(`${API_BASE}/api/audit-events?limit=30`, { credentials: "include" })
      .then(async (response) => {
        if (!response.ok) throw new Error(t("configLoadError"));
        const result = await response.json();
        if (requestId === activeRequest.current) setItems(result.items || []);
      }).catch((loadError) => {
        if (requestId === activeRequest.current) setError(loadError.message || t("configLoadError"));
      });
    return () => { if (requestId === activeRequest.current) activeRequest.current += 1; };
  }, [userId]);
  async function showDetails(id) {
    setError("");
    const requestId = ++activeRequest.current;
    try {
      const response = await fetch(`${API_BASE}/api/audit-events/${id}`, { credentials: "include" });
      if (!response.ok) throw new Error(t("configLoadError"));
      const result = await response.json();
      if (requestId === activeRequest.current) setSelected(result);
    } catch (loadError) {
      if (requestId === activeRequest.current) setError(loadError.message || t("configLoadError"));
    }
  }
  return <section className="panel governance-panel"><div className="panel-head"><div>
    <div className="eyebrow">{t("controls")}</div><h2>{t("audit")}</h2></div></div>
    {error && <p className="config-error" role="alert">{error}</p>}
    <div className="table-scroll"><table><thead><tr><th>{t("dateLabel")}</th><th>{t("userLabel")}</th>
      <th>{t("actionLabel")}</th><th>{t("targetLabel")}</th><th>{t("detailLabel")}</th></tr></thead>
      <tbody>{items.map((item) => <tr key={item.id}><td>{displayDate(item.event_at)}</td>
        <td>{roleLabel(locale, item.actor_role)} #{item.actor_id ?? "—"}</td><td><AuditOperation action={item.action} locale={locale} t={t}/></td>
        <td>{item.object_type} #{item.object_id_text || item.object_id || "—"}</td>
        <td><button className="text-button" onClick={() => showDetails(item.id)}>{t("detailLabel")}</button></td>
      </tr>)}</tbody></table>
      {!items.length && !error && <div className="empty-state">{t("noRows")}</div>}</div>
    {selected && <details className="audit-detail" open><summary>{t("detailLabel")} #{selected.id}</summary>
      <p>{selected.reason}</p><small>{selected.previous_hash} → {selected.event_hash}</small></details>}
  </section>;
}
// These Japanese reasons are supplied by the backend fixtures. Reviewed expenses have no language field.
const JAPANESE_EXPENSE_REASONS = new Set([
  "申請内容の補足資料を確認してください。",
  "利用日と申請内容の確認が必要です。",
]);

function ExpensePanel({ data, t, role, accountRole, locale }) {
  const [items, setItems] = useState([]);
  const [categories, setCategories] = useState([]);
  const [category, setCategory] = useState("");
  const [amount, setAmount] = useState("");
  const [description, setDescription] = useState("");
  const [expenseDate, setExpenseDate] = useState(todayJst());
  const [receipt, setReceipt] = useState(null);
  const [receiptInputKey, setReceiptInputKey] = useState(0);
  const [rowReceipts, setRowReceipts] = useState({});
  const [rejectReason, setRejectReason] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function load() {
    const response = await fetch(`${API_BASE}/api/expenses`, { credentials: "include" });
    if (!response.ok) throw new Error(t("configLoadError"));
    const result = await response.json();
    setItems(result.items || []);
    setCategories(result.allowed_categories || []);
    setCategory((current) => current || result.allowed_categories?.[0] || "");
  }
  useEffect(() => {
    let active = true;
    setItems([]);
    setError("");
    fetch(`${API_BASE}/api/expenses`, { credentials: "include" })
      .then(async (response) => {
        if (!response.ok) throw new Error(t("configLoadError"));
        const result = await response.json();
        if (!active) return;
        setItems(result.items || []);
        setCategories(result.allowed_categories || []);
        setCategory((current) => current || result.allowed_categories?.[0] || "");
      }).catch((loadError) => { if (active) setError(loadError.message || t("configLoadError")); });
    return () => { active = false; };
  }, [role, data.user.id]);
  function categoryLabel(value) {
    if (locale !== "zh") return value;
    return ({ "交通費": "交通费", "消耗品費": "办公耗材", "会議費": "会议费",
      "通信費": "通信费", "その他": "其他" })[value] || value;
  }
  async function request(url, method, body, isForm = false) {
    const response = await fetch(`${API_BASE}${url}`, {
      method, credentials: "include",
      headers: isForm ? undefined : { "Content-Type": "application/json" },
      body: body ? (isForm ? body : JSON.stringify(body)) : undefined,
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.detail || t("error"));
    return result;
  }
  async function upload(expense, file) {
    const body = new FormData();
    body.append("version", String(expense.version));
    body.append("receipt", file);
    await request(`/api/expenses/${expense.id}/receipt`, "POST", body, true);
    await load();
  }
  async function create(event) {
    event.preventDefault();
    const form = event.currentTarget;
    setBusy(true); setError("");
    try {
      const created = await request("/api/expenses", "POST", {
        category, amount: Number(amount), description, expense_date: expenseDate,
      });
      if (receipt) await upload({ id: created.id, version: created.version }, receipt);
      form.reset();
      setAmount(""); setDescription(""); setReceipt(null);
      setReceiptInputKey((key) => key + 1);
      await load();
    } catch (requestError) { setError(requestError.message || t("error")); }
    finally { setBusy(false); }
  }
  async function action(expense, actionName, body = {}) {
    setBusy(true); setError("");
    try {
      await request(`/api/expenses/${expense.id}/${actionName}`, "POST", { version: expense.version, ...body });
      await load();
    } catch (requestError) { setError(requestError.message || t("error")); }
    finally { setBusy(false); }
  }
  const maySubmit = ["advisor", "manager", "hq_finance", "executive"].includes(role);
  const mayApprove = ["store_manager", "finance", "executive", "administrator"].includes(accountRole);
  const mayRecord = ["finance", "executive", "administrator"].includes(accountRole);
  return <section className="panel expense-panel"><div className="panel-head"><div>
    <div className="eyebrow">{t("settings")}</div><h2>{t("expenses")}</h2></div></div>
    {error && <p className="config-error" role="alert">{error}</p>}
    {maySubmit && <form className="expense-form" onSubmit={create}>
      <label>{t("expenseCategory")}<select value={category} onChange={(event) => setCategory(event.target.value)} required>
        {categories.map((item) => <option value={item} key={item}>{categoryLabel(item)}</option>)}</select></label>
      <label>{t("expenseAmount")}<input type="number" min="1" max="100000000" value={amount}
        onChange={(event) => setAmount(event.target.value)} required/></label>
      <label>{t("expenseDate")}<input type="date" value={expenseDate}
        onChange={(event) => setExpenseDate(event.target.value)} required/></label>
      <label>{t("expenseDescription")}<input value={description}
        onChange={(event) => setDescription(event.target.value)} maxLength={2000} required/></label>
      <label>{t("attachReceipt")}<input key={receiptInputKey} type="file" accept=".pdf,.jpg,.jpeg,.png" required
        onChange={(event) => setReceipt(event.target.files?.[0] || null)}/></label>
      <button className="primary-btn" disabled={busy || !categories.length}>{t("createDraft")}</button>
    </form>}
    {mayApprove && <label className="expense-reason">{t("expenseReason")}<input value={rejectReason}
      onChange={(event) => setRejectReason(event.target.value)}/></label>}
    <div className="table-scroll"><table><thead><tr><th>{t("userLabel")}</th><th>{t("expenseCategory")}</th>
      <th>{t("expenseAmount")}（{t("taxInclusive")}）</th><th>{t("consumptionTax")}</th>
      <th>{t("expenseDate")} / {t("appliedAt")}</th><th>{t("status")}</th>
      <th>{t("recordedProof")}</th><th>{t("actionLabel")}</th></tr></thead>
      <tbody>{items.map((item) => <tr key={item.id}><td>{item.applicant_name}</td><td>{categoryLabel(item.category)}</td>
        <td>¥{Number(item.amount).toLocaleString()}</td><td>¥{Number(item.tax_amount || 0).toLocaleString()} · {item.tax_category}</td>
        <td>{displayDate(item.expense_date)}<br/>{t("appliedAt")}: {displayDate(item.applied_at)}</td>
        <td>{t(`expenseStatus${item.status}`)}{item.rejection_reason?.trim() && <small className="text-danger expense-rejection">
          <OriginalText value={item.rejection_reason} sourceLocale={JAPANESE_EXPENSE_REASONS.has(item.rejection_reason) ? "ja" : undefined} locale={locale} t={t}/>
        </small>}</td>
        <td>{item.accounting_integration_id || item.recorded_reference || "—"}{item.recorded_confirmed_at && <small><br/>{displayDate(item.recorded_confirmed_at)}</small>}</td>
        <td className="expense-actions">
          {item.receipt_filename && <a href={`${API_BASE}/api/expenses/${item.id}/receipt`} target="_blank" rel="noreferrer">{t("receipt")}</a>}
          {item.applicant_id === data.user.id && ["DRAFT", "REJECTED"].includes(item.status) && <>
            <input aria-label={t("attachReceipt")} type="file" accept=".pdf,.jpg,.jpeg,.png"
              onChange={(event) => setRowReceipts((current) => ({ ...current, [item.id]: event.target.files?.[0] || null }))}/>
            <button disabled={busy || !rowReceipts[item.id]} onClick={() => upload(item, rowReceipts[item.id]).catch((e) => setError(e.message))}>{t("attachReceipt")}</button>
            {item.receipt_filename && <button disabled={busy} onClick={() => action(item, "submit")}>{t("submitExpense")}</button>}
          </>}
          {item.status === "SUBMITTED" && mayApprove && <>
            <button disabled={busy} onClick={() => action(item, "approve")}>{t("approveExpense")}</button>
            <button disabled={busy || !rejectReason.trim()} onClick={() => action(item, "reject", { reason: rejectReason })}>{t("rejectExpense")}</button>
          </>}
          {item.status === "APPROVED" && mayRecord &&
            <button disabled={busy} onClick={() => action(item, "record")}>{t("recordExpense")}</button>}
        </td></tr>)}</tbody></table>
      {!items.length && !error && <div className="empty-state">{t("noRows")}</div>}</div>
  </section>;
}
function DataExchangePanel({ data, t, locale }) {
  const importFileInput = useRef(null);
  const [jobs, setJobs] = useState([]);
  const [resource, setResource] = useState("households");
  const [format, setFormat] = useState("csv");
  const [includePersonalData, setIncludePersonalData] = useState(false);
  const [importFile, setImportFile] = useState(null);
  const [importMapping, setImportMapping] = useState({});
  const [previewResult, setPreviewResult] = useState(null);
  const [importResult, setImportResult] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const accountRole = data.account_role;
  const canImport = ["administrator", "hq_staff"].includes(accountRole);
  const canExportFinance = ["administrator", "executive", "finance", "hq_staff"].includes(accountRole);
  const canIncludePersonal = ["administrator", "executive"].includes(accountRole);
  const options = [["households", "exportHouseholds"], ["introductions", "exportIntroductions"],
    ["expenses", "exportExpenses"]];
  if (canExportFinance) options.push(["fee_entitlements", "exportFees"], ["invoice_data", "exportInvoices"]);
  const tResource = (key) => t(`export${key[0].toUpperCase()}${key.slice(1)}`);
  async function loadJobs(active = () => true) {
    const response = await fetch(`${API_BASE}/api/export-jobs`, { credentials: "include" });
    if (!response.ok) throw new Error(t("configLoadError"));
    const result = await response.json();
    if (active()) setJobs(result.items || []);
  }
  useEffect(() => {
    let active = true;
    setJobs([]);
    setImportResult(null);
    setError("");
    if (!canIncludePersonal) setIncludePersonalData(false);
    if (!options.some(([key]) => key === resource)) setResource("households");
    loadJobs(() => active).catch((loadError) => { if (active) setError(loadError.message); });
    return () => { active = false; };
  }, [data.user.id]);
  const resourceLabels = {
    households: t("exportHouseholds"), introductions: t("exportIntroductions"),
    expenses: t("exportExpenses"), fee_entitlements: t("exportFees"), invoice_data: t("exportInvoices"),
  };
  async function createExport(event) {
    event.preventDefault();
    setBusy(true); setError("");
    try {
      const response = await fetch(`${API_BASE}/api/export-jobs`, {
        method: "POST", credentials: "include", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ resource, include_personal_data: includePersonalData, format }),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.detail || t("error"));
      await loadJobs();
    } catch (requestError) { setError(requestError.message || t("error")); }
    finally { setBusy(false); }
  }
  const importFields = [
    ["external_id", "importExternalId"], ["representative_name", "importRepresentative"],
    ["store_id", "importStore"], ["advisor_employee_code", "importAdvisorCode"],
    ["budget_band", "importBudget"], ["area_pref", "importArea"],
  ];
  const previewMatchesMapping = previewResult && importFields.every(([key]) =>
    (previewResult.mapping?.[key] || "") === (importMapping[key] || ""));
  async function previewCsv() {
    if (!importFile) return;
    setBusy(true); setError(""); setImportResult(null);
    try {
      const body = new FormData();
      body.append("file", importFile);
      body.append("mapping_json", JSON.stringify(importMapping));
      const response = await fetch(`${API_BASE}/api/imports/kintone/preview`, {
        method: "POST", credentials: "include", body,
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.detail || t("error"));
      setPreviewResult(result);
      setImportMapping(result.mapping || {});
    } catch (requestError) { setError(requestError.message || t("error")); }
    finally { setBusy(false); }
  }
  async function importCsv() {
    if (!importFile || !previewResult || !previewMatchesMapping) {
      setError(t("previewRequired"));
      return;
    }
    setBusy(true); setError("");
    try {
      const body = new FormData();
      body.append("file", importFile);
      body.append("preview_job_id", previewResult.id);
      body.append("mapping_json", JSON.stringify(importMapping));
      const response = await fetch(`${API_BASE}/api/imports/kintone`, {
        method: "POST", credentials: "include", body,
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.detail || t("error"));
      const detailResponse = await fetch(`${API_BASE}/api/import-jobs/${result.id}`, { credentials: "include" });
      if (!detailResponse.ok) throw new Error(t("configLoadError"));
      setImportResult(await detailResponse.json());
      setImportFile(null);
      if (importFileInput.current) importFileInput.current.value = "";
      setPreviewResult(null);
      setImportMapping({});
    } catch (requestError) { setError(requestError.message || t("error")); }
    finally { setBusy(false); }
  }
  const reasonZh = {
    "既に取り込み済みです": "已导入，跳过。",
    "店舗が見つかりません": "找不到门店。",
    "store_id は数値で指定してください": "store_id 必须为数字。",
    "external_id は1〜160文字で指定してください": "external_id 长度须为 1–160 个字符。",
    "代表者名は1〜120文字で指定してください": "代表者姓名长度须为 1–120 个字符。",
    "必須項目 external_id、representative_name、store_id をCSV列へ割り当ててください": "请将必填字段 external_id、representative_name、store_id 映射到 CSV 列。",
    "担当顧問が店舗と一致しないか、有効なアカウントではありません": "负责顾问与门店不匹配或账号无效。",
    "同じCSV内に同一external_idがあります": "CSV 内存在重复的 external_id。",
    "予算帯または希望エリアが文字数上限を超えています": "预算范围或意向区域超出字符数限制。",
  };
  const importReason = (reason) => locale === "zh" ? reasonZh[reason] || reason : reason;
  return <section className="panel data-exchange-panel"><div className="panel-head"><div>
    <div className="eyebrow">{t("settings")}</div><h2>{t("dataExchange")}</h2></div></div>
    {error && <p className="config-error" role="alert">{error}</p>}
    <form className="export-form" onSubmit={createExport}>
      <label>{t("exportResource")}<select value={resource} onChange={(event) => setResource(event.target.value)}>
        {options.map(([key, label]) => <option value={key} key={key}>{t(label)}</option>)}</select></label>
      <label>{t("exportFormat")}<select value={format} onChange={(event) => setFormat(event.target.value)}>
        <option value="csv">{t("formatCsv")}</option><option value="pdf">{t("formatPdf")}</option></select></label>
      {canIncludePersonal && <label className="inline-check"><input type="checkbox" checked={includePersonalData}
        onChange={(event) => setIncludePersonalData(event.target.checked)}/>{t("includePersonalData")}</label>}
      <button className="primary-btn" disabled={busy}>{t("exportFile")}</button>
    </form>
    <div className="export-job-list">{jobs.map((job) => <div key={job.id}>
      <span>{resourceLabels[job.resource] || job.resource} · {String(job.format || "csv").toUpperCase()} · {job.row_count} · {job.status}</span>
      {job.status === "READY" && <a href={`${API_BASE}/api/export-jobs/${job.id}/download`}>{t("downloadCsv")}</a>}
    </div>)}</div>
    {canImport && <div className="import-form">
      <label>{t("kintoneCsv")}<input ref={importFileInput} type="file" accept=".csv,text/csv" required
        onChange={(event) => {
          setImportFile(event.target.files?.[0] || null);
          setPreviewResult(null); setImportMapping({}); setImportResult(null);
        }}/></label>
      {previewResult && <div className="import-mapping"><h3>{t("importFieldMapping")}</h3>
        <div className="import-mapping-grid">{importFields.map(([key, label]) => <label key={key}>{t(label)}
          <select value={importMapping[key] || ""} onChange={(event) => {
            setImportMapping((current) => ({ ...current, [key]: event.target.value }));
          }}>
            <option value="">{t("importUnmapped")}</option>
            {previewResult.headers.filter((header) => !importFields.some(([otherKey]) =>
              otherKey !== key && importMapping[otherKey] === header))
              .map((header) => <option value={header} key={`${key}-${header}`}>{header}</option>)}
          </select></label>)}</div>
        <p className="config-note">{previewMatchesMapping ? t("previewExpiry") : t("previewStale")}</p>
        <div className="import-preview-counts">
          <span>{t("previewReady")}: {previewResult.ready_rows}</span>
          <span>{t("skippedRows")}: {previewResult.skipped_rows}</span>
          <span>{t("errorRows")}: {previewResult.error_rows}</span>
          {previewResult.truncated && <span>{t("truncated")}</span>}
        </div>
        <div className="import-preview-actions">
          <button type="button" className="secondary-btn" disabled={busy || !importFile} onClick={previewCsv}>{t("runDryRun")}</button>
          <button type="button" className="primary-btn" disabled={busy || !previewMatchesMapping || !previewResult.ready_rows}
            onClick={importCsv}>{t("confirmImport")}</button>
        </div>
        <ImportResultTable rows={previewResult.rows} t={t} locale={locale} importReason={importReason}/>
      </div>}
      {!previewResult && <button type="button" className="secondary-btn" disabled={busy || !importFile} onClick={previewCsv}>{t("runDryRun")}</button>}
    </div>}
    {resource === "invoice_data" && <p className="config-note">{t("invoiceCsvNote")}</p>}
    {importResult && <div className="import-result"><h3>{t("importResults")} · {importResult.status}</h3>
      <p>{t("importedRows")}: {importResult.success_rows} · {t("skippedRows")}: {importResult.skipped_rows} · {t("errorRows")}: {importResult.error_rows}</p>
      <ImportResultTable rows={importResult.rows} t={t} locale={locale} importReason={importReason}/>
    </div>}
  </section>;
}
function ImportResultTable({ rows, t, importReason }) {
  return <div className="table-scroll"><table><thead><tr><th>#</th><th>external_id</th><th>{t("status")}</th><th>{t("detailLabel")}</th></tr></thead>
    <tbody>{(rows || []).map((row) => <tr key={row.source_row_number}>
      <td>{row.source_row_number}</td><td>{row.external_id}</td>
      <td>{t(row.status === "READY" ? "previewReady" : `importStatus${row.status}`)}</td><td>{importReason(row.reason)}</td>
    </tr>)}</tbody></table></div>;
}
function SettingsPage({ data, t, role, locale, onLocaleChange, onReset, onConfigSaved, preferences, onSavePreferences, sampleMode }) {
  return <div className="admin-page settings-page"><PageTitle eyebrow={t("systemPreferences")} title={t("settings")} sub={t("settingsSub")}/>
    <div className="settings-grid"><section className="panel setting-card"><div className="setting-icon"><Users size={19}/></div><div><h2>{t("role")}</h2><p>{t("currentRole")}：{roleLabel(locale, role)}。{t("roleDescription")}</p>
      <div className="setting-roles">{data.roles.map((r) => <span className={`role-chip ${r.id === role ? "current" : ""}`} key={r.id}>{roleLabel(locale, r.id)} {r.id === role && <Check size={13}/>}</span>)}</div></div></section>
      <section className="panel setting-card"><div className="setting-icon"><Languages size={19}/></div><div><h2>{t("language")}</h2><p>{t("languageDescription")}</p><select className="settings-locale" aria-label={t("language")} value={locale} onChange={(event) => onLocaleChange(event.target.value)}><option value="ja">日本語</option><option value="zh">中文</option></select></div></section>
      <section className="panel setting-card"><div className="setting-icon"><ShieldCheck size={19}/></div><div><h2>{t("consent")}</h2><p>{t("consentDescription")}</p><span className="pill pill-green">{t("l1Protected")}</span></div></section>
      <section className="panel setting-card danger-setting"><div className="setting-icon danger"><Settings size={19}/></div><div><h2>{t("reset")}</h2><p>{t("resetDescription")}</p><button className="danger-btn" disabled={role !== "hq_finance"} onClick={onReset}>{t("reset")}</button>{role !== "hq_finance" && <small>{t("financeRoleOnly")}</small>}</div></section>
    </div>
    <PreferencePanel preferences={preferences} t={t} onSave={onSavePreferences}/>
    <AuditTrailPanel t={t} userId={data.user.id} locale={locale}/>
    <ExpensePanel data={data} t={t} role={role} accountRole={data.account_role} locale={locale}/>
    {!sampleMode && <DataExchangePanel data={data} t={t} locale={locale}/>}
    {!sampleMode && <MonthClosePanel accountRole={data.account_role} userId={data.user.id} t={t}/>}
    {!sampleMode && <DataCorrectionPanel accountRole={data.account_role} t={t} locale={locale}/>}
    <OperationsPanel accountRole={data.account_role} locale={locale} t={t}/>
    <section className="panel config-panel"><div className="panel-head"><div><div className="eyebrow">{t("versionedOperations")}</div><h2>{t("systemConfig")}</h2></div><ShieldCheck size={17} className="green-text"/></div>
      {role === "hq_finance" ? <SystemConfigPanel role={role} locale={locale} t={t} onSaved={onConfigSaved}/> :
        <p className="config-permission">{t("configPermission")}</p>}
      <p className="config-note">{t("slaPending")} {t("accountingNote")}</p>
    </section>
  </div>;
}

function MonthClosePanel({ accountRole, userId, t }) {
  const canAccess = ["finance", "executive", "administrator", "hq_staff"].includes(accountRole);
  const canPrepare = ["finance", "administrator", "hq_staff"].includes(accountRole);
  const canApprove = ["executive", "administrator"].includes(accountRole);
  const [period, setPeriod] = useState(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  });
  const [items, setItems] = useState([]);
  const [locks, setLocks] = useState([]);
  const [selected, setSelected] = useState(null);
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const statusLabels = {
    PREPARED: t("closePrepared"), CLOSED: t("closeClosed"),
    REOPEN_REQUESTED: t("reopenRequested"), REOPENED: t("reopened"),
  };
  async function load() {
    const [closeResponse, lockResponse] = await Promise.all([
      fetch(`${API_BASE}/api/month-closes?period=${encodeURIComponent(period)}`, { credentials: "include" }),
      fetch(`${API_BASE}/api/month-closes/lock-matrix?period=${encodeURIComponent(period)}`, { credentials: "include" }),
    ]);
    if (!closeResponse.ok || !lockResponse.ok) throw new Error(t("monthCloseError"));
    const [closeData, lockData] = await Promise.all([closeResponse.json(), lockResponse.json()]);
    setItems(closeData.items);
    setLocks(lockData.items);
    setSelected((current) => current ? closeData.items.find((item) => item.id === current.id) || null : null);
  }
  useEffect(() => {
    if (!canAccess) return;
    load().catch((loadError) => setError(loadError.message || t("monthCloseError")));
  }, [period, canAccess, accountRole]);
  async function action(path, body) {
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE}${path}`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      });
      if (!response.ok) throw new Error(t("monthCloseError"));
      const result = await response.json();
      if (result.snapshot) setSelected({ ...result, snapshot: result.snapshot });
      setReason("");
      await load();
    } catch (actionError) { setError(actionError.message || t("monthCloseError")); }
    finally { setBusy(false); }
  }
  async function showSnapshot(item) {
    try {
      const response = await fetch(`${API_BASE}/api/month-closes/${item.id}/detail`, { credentials: "include" });
      if (!response.ok) throw new Error(t("monthCloseError"));
      setSelected(await response.json());
      setError("");
    } catch (loadError) { setError(loadError.message || t("monthCloseError")); }
  }
  if (!canAccess) return null;
  const latest = items[0];
  const active = selected || latest;
  const status = active?.status;
  const version = active?.version;
  const mayClose = canApprove && status === "PREPARED" && active.prepared_by !== userId;
  const mayRequestReopen = canPrepare && status === "CLOSED";
  const mayApproveReopen = canApprove && status === "REOPEN_REQUESTED" && active.reopen_requested_by !== userId;
  const resourceLabels = {
    expenses: t("expenses"), fee_entitlements: t("revenueLedger"), contracts: t("contract"),
    construction_projects: t("constructionConfirmation"), activities: t("activities"),
    introductions: t("introduction"), stage_events: t("stages"),
  };
  return <section className="panel month-close-panel">
    <div className="panel-head"><div><div className="eyebrow">{t("systemPreferences")}</div><h2>{t("monthClose")}</h2></div></div>
    <p className="config-note">{t("monthCloseDescription")} {t("accountingNotDeveloped")}</p>
    {error && <p className="config-error" role="alert">{error}</p>}
    <div className="month-close-controls">
      <label>{t("closePeriod")}<input type="month" value={period} onChange={(event) => {
        setPeriod(event.target.value); setSelected(null); setError("");
      }}/></label>
      {canPrepare && (!latest || latest.status === "REOPENED") &&
        <button className="primary-btn" disabled={busy} onClick={() => action("/api/month-closes/prepare", { period })}>
          {t("prepareClose")}</button>}
      {mayClose && <button className="primary-btn" disabled={busy}
        onClick={() => action(`/api/month-closes/${active.id}/close`, { version })}>{t("closePeriodAction")}</button>}
      {mayRequestReopen && <div className="month-reopen-action">
        <input value={reason} onChange={(event) => setReason(event.target.value)} minLength={10} maxLength={1000}
          placeholder={t("reopenReason")}/>
        <button className="secondary-btn" disabled={busy || reason.trim().length < 10}
          onClick={() => action(`/api/month-closes/${active.id}/request-reopen`, { version, reason })}>{t("requestReopen")}</button>
      </div>}
      {mayApproveReopen && <button className="primary-btn" disabled={busy}
        onClick={() => action(`/api/month-closes/${active.id}/approve-reopen`, { version })}>{t("approveReopen")}</button>}
    </div>
    <div className="month-close-layout">
      <div className="month-close-history"><h3>{t("monthClose")}</h3>
        {items.length ? items.map((item) => <button key={item.id} className={`month-close-item ${active?.id === item.id ? "selected" : ""}`}
          onClick={() => showSnapshot(item)}><span>{displayDate(item.period)} · v{item.snapshot_version}</span>
          <b>{statusLabels[item.status] || item.status}</b></button>) :
          <p className="empty-state">{t("monthCloseEmpty")}</p>}
      </div>
      <div className="month-close-detail">
        {active ? <><div className="month-close-meta"><span>{statusLabels[active.status] || active.status} · v{active.snapshot_version}</span>
          <small>{t("snapshotHash")}: {active.snapshot_sha256}</small></div>
          {selected?.snapshot && <details open><summary>{t("snapshotDetails")}</summary>
            <pre>{JSON.stringify(selected.snapshot, null, 2)}</pre></details>}</> :
          <p className="empty-state">{t("monthCloseEmpty")}</p>}
        <h3>{t("lockedRecords")}</h3>
        <div className="month-lock-list">{locks.map((item) => <span key={item.resource}>
          {resourceLabels[item.resource] || item.resource} · {item.locked ? t("locked") : t("unlocked")}</span>)}</div>
      </div>
    </div>
    {status === "PREPARED" && active?.prepared_by === userId && <small className="config-note">{t("separateApproval")}</small>}
  </section>;
}

function DataCorrectionPanel({ accountRole, t, locale }) {
  const canReview = ["finance", "executive", "administrator", "hq_staff", "store_manager"].includes(accountRole);
  const [items, setItems] = useState([]);
  const [notes, setNotes] = useState({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  async function load() {
    const response = await fetch(`${API_BASE}/api/data-corrections?status=PENDING`, { credentials: "include" });
    if (!response.ok) throw new Error(t("monthCloseError"));
    const result = await response.json();
    setItems(result.items);
  }
  useEffect(() => {
    if (canReview) load().catch((loadError) => setError(loadError.message || t("error")));
  }, [canReview, accountRole]);
  async function decide(item, action) {
    setBusy(item.id);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/api/data-corrections/${item.id}/decision`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ version: item.version, action, note: notes[item.id] || "" }),
      });
      if (!response.ok) throw new Error(t("monthCloseError"));
      setNotes((current) => ({ ...current, [item.id]: "" }));
      await load();
    } catch (decisionError) { setError(decisionError.message || t("error")); }
    finally { setBusy(""); }
  }
  if (!canReview) return null;
  const fieldLabels = {
    representative_name: t("correctionRepresentative"), area_pref: t("correctionArea"),
    budget_band: t("correctionBudget"), land_status: t("correctionLand"),
  };
  return <section className="panel data-correction-panel">
    <div className="panel-head"><div><div className="eyebrow">{t("governance")}</div><h2>{t("correctionPending")}</h2></div>
      <button className="mini-action" disabled={busy !== ""} onClick={() => load().catch((loadError) => setError(loadError.message || t("error")))}>{t("opsRefresh")}</button></div>
    {error && <p className="config-error" role="alert">{error}</p>}
    {items.length ? items.map((item) => <article className="correction-card" key={item.id}>
      <div><b>{item.household_code} · {item.representative_name}</b><span>{item.requester_name} · {displayDate(item.requested_at)}</span></div>
      <div className="correction-values"><strong>{fieldLabels[item.field_name] || item.field_name}</strong>
        <span>{item.before_value || "—"} → {item.requested_value}</span><small>{item.reason}</small></div>
      <label>{t("correctionReason")}<input value={notes[item.id] || ""} maxLength={500}
        onChange={(event) => setNotes((current) => ({ ...current, [item.id]: event.target.value }))}/></label>
      <div className="form-actions"><button className="danger-btn" disabled={busy !== "" || (notes[item.id] || "").trim().length < 10}
        onClick={() => decide(item, "reject")}>{t("correctionReject")}</button>
        <button className="primary-btn" disabled={busy !== ""} onClick={() => decide(item, "approve")}>{t("correctionApprove")}</button></div>
    </article>) : <p className="empty-state">{t("noRows")}</p>}
  </section>;
}

function OperationsPanel({ accountRole, locale, t }) {
  const canView = ["administrator", "executive", "finance", "hq_staff"].includes(accountRole);
  const [status, setStatus] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function refresh() {
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/api/operations/status`, { credentials: "include" });
      if (!response.ok) throw new Error(t("monthCloseError"));
      setStatus(await response.json());
    } catch (loadError) { setError(loadError.message || t("error")); }
    finally { setBusy(false); }
  }
  useEffect(() => { if (canView) refresh(); }, [canView, accountRole]);
  if (!canView) return null;
  const cards = status ? [
    [t("opsDatabase"), status.database],
    [t("opsAuditChain"), status.audit_chain === "OK" ? t("opsOk") : t("opsDegraded")],
    [t("opsOutbox"), status.outbox_pending],
    [t("opsDeadLetters"), status.outbox_dead_letters],
    [t("opsExpiredExports"), status.expired_exports_ready_for_cleanup],
    [t("opsSessionCount"), status.active_sessions],
    [t("opsFallbackTasks"), status.notification_fallback_tasks],
    [t("opsEmail"), t("opsNotConfigured")],
    [t("opsSeedBatch"), status.seed_batch || "—"],
  ] : [];
  return <section className="panel operations-status-panel">
    <div className="panel-head"><div><div className="eyebrow">{t("governance")}</div><h2>{t("dataOps")}</h2></div>
      <button className="mini-action" disabled={busy} onClick={refresh}>{busy ? "…" : t("opsRefresh")}</button></div>
    {error && <p className="config-error" role="alert">{error}</p>}
    {status && <><p className="config-note">{t("opsRefreshTime")}: {displayDate(status.generated_at)}</p>
      <div className="ops-status-grid">{cards.map(([label, value]) => <div key={label}>
        <span>{label}</span><b className={value === t("opsDegraded") || value === "DEGRADED" ? "ops-degraded" : ""}>{value}</b>
      </div>)}</div></>}
  </section>;
}

function PreferencePanel({ preferences, t, onSave }) {
  const [widgets, setWidgets] = useState(preferences.dashboard_widgets);
  const [notifications, setNotifications] = useState(preferences.notification_preferences);
  useEffect(() => { setWidgets(preferences.dashboard_widgets); setNotifications(preferences.notification_preferences); }, [preferences]);
  function toggleWidget(widget) {
    setWidgets((current) => current.includes(widget) ? current.filter((item) => item !== widget)
      : current.length < 4 ? [...current, widget] : current);
  }
  return <section className="panel preference-panel"><div className="panel-head"><div><div className="eyebrow">{t("personalWorkspace")}</div><h2>{t("dashboardPrefs")}</h2></div></div>
    <div className="preference-options">{[["tasks", t("taskQueues")], ["overview", t("pipeline")], ["trend", t("trendEntry")], ["report", t("dailyReport")]].map(([key, label]) =>
      <label key={key}><input type="checkbox" checked={widgets.includes(key)} onChange={() => toggleWidget(key)}/>{label}</label>)}</div>
    <h3>{t("notificationPrefs")}</h3><div className="preference-options">
      {["in_app", "email"].map((key) => <label key={key}><input type="checkbox" checked={Boolean(notifications[key])}
        onChange={(event) => setNotifications((current) => ({ ...current, [key]: event.target.checked }))}/>
        {t(key === "in_app" ? "inApp" : "emailNotice")}</label>)}</div>
    <p className="config-note">{t("emailFallbackNote")}</p>
    <button className="secondary-btn" onClick={() => onSave({ dashboard_widgets: widgets, notification_preferences: notifications })}>
      <Check size={15}/>{t("savePreferences")}</button>
  </section>;
}

function SystemConfigPanel({ role, locale, t, onSaved }) {
  const [items, setItems] = useState([]);
  const [drafts, setDrafts] = useState({});
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState("");
  useEffect(() => {
    fetch(`${API_BASE}/api/system-config`, { credentials: "include" })
      .then(async (response) => {
        if (!response.ok) throw new Error(t("configLoadError"));
        return response.json();
      })
      .then((result) => {
        setItems(result.items);
        setDrafts(Object.fromEntries(result.items.map((item) => [item.key, JSON.stringify(item.value, null, 2)])));
      })
      .catch((loadError) => setError(loadError.message || t("configLoadError")));
  }, [role, locale]);
  async function save(item) {
    setError("");
    let value;
    try { value = JSON.parse(drafts[item.key]); }
    catch { setError(locale === "ja" ? "JSON形式を確認してください。" : "请检查 JSON 格式。"); return; }
    setSaving(item.key);
    try {
      const response = await fetch(`${API_BASE}/api/system-config/${encodeURIComponent(item.key)}`, {
        method: "PUT",
        credentials: "include", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ value, reason }),
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}));
        throw new Error(detail.detail || t("error"));
      }
      setItems((current) => current.map((entry) => entry.key === item.key
        ? { ...entry, value, updated_at: new Date().toISOString() } : entry));
      setReason("");
      onSaved();
    } catch (saveError) { setError(saveError.message || t("error")); }
    finally { setSaving(""); }
  }
  return <><label className="config-reason"><span>{t("changeReason")}</span>
      <input value={reason} onChange={(event) => setReason(event.target.value)} maxLength={500}/>
    </label>
    {error && <div className="config-error" role="alert">{error}</div>}
    <div className="config-list">{items.map((item) => <div className="config-row" key={item.key}>
      <label><span>{CONFIG_LABELS[locale][item.key]}</span><textarea rows={2} value={drafts[item.key] || ""}
        onChange={(event) => setDrafts((current) => ({ ...current, [item.key]: event.target.value }))}/></label>
      <button className="mini-action" disabled={reason.trim().length < 10 || saving !== ""}
        onClick={() => save(item)}>{saving === item.key ? "…" : t("saveConfig")}</button>
    </div>)}</div>
  </>;
}
function HouseholdModal({ locale, household: h, t, role, onClose, onActivity, api }) {
  const [stage, setStage] = useState(h.stage_events.at(-1)?.to_stage || "新規予約");
  const [disputeIntro, setDisputeIntro] = useState(null);
  const currentStage = h.stage_events.at(-1)?.to_stage;
  const hasStageTimestamps = h.stage_events.some((event) => event.changed_at);
  const stageHistory = hasStageTimestamps ? [...h.stage_events].sort((a, b) => String(a.changed_at || "").localeCompare(String(b.changed_at || ""))) : h.stage_events;
  return <Modal onClose={onClose} wide label={t("household360")} closeLabel={t("close")} heading={<div>
    <div className="eyebrow">{t("household360")} · #{String(h.id).padStart(4, "0")}</div>
    <div className="household-name-stage"><h2>{h.representative_name}</h2><span className={stageTagClass(currentStage)}>{localeLabel(locale, currentStage)}</span></div>
    <p>{h.store_name} · {h.advisor_name} · {h.area_pref}</p>
  </div>}>
    <div className="household-facts"><Fact label={t("budget")} value={h.budget_band}/><Fact label={t("area")} value={h.area_pref}/><Fact label={t("land")} value={h.land_status}/><Fact label={t("stage")} value={localeLabel(locale, currentStage)}/></div>
    <div className="household-modal-grid"><div className="modal-column"><section className="modal-section"><div className="section-title"><h3>{t("people")}</h3><span className="count-badge">{h.persons.length}</span></div>
      {h.persons.map((p) => <div className="person-row" key={p.id}><div className="customer-avatar">{p.name.slice(0, 1)}</div><div><b>{p.name}</b><span>{p.relation} · {p.phone}</span></div></div>)}</section>
      <section className="modal-section"><div className="section-title"><h3>{t("firstTouch")} / {t("latestTouch")}</h3></div><div className="touch-compare">{[["first", h.first_touch], ["last", h.latest_touch]].map(([key, touch]) => <div className="touch-card" key={key}><small>{t(key)}</small><b>{touch?.channel || "—"}</b><span>{displayDate(touch?.touch_at)}</span><em>{touch?.capture_method || "—"}</em></div>)}</div></section>
      <section className="modal-section"><div className="section-title"><h3>{t("stages")}</h3><div className="inline-stage"><select value={stage} onChange={(e) => setStage(e.target.value)}>{h.stage_events.length ? h.stage_events.map((e, i) => <option key={`${e.id}-${i}`} value={e.to_stage}>{localeLabel(locale, e.to_stage)}</option>) : ["新規予約", "初回相談済", "FP診断済", "紹介済", "訪問・商談中", "契約", "着工", "完了・見送り"].map((s) => <option key={s} value={s}>{localeLabel(locale, s)}</option>)}</select><button className="mini-action" onClick={() => api(`/api/households/${h.id}/stage`, "POST", { to_stage: stage })}>{t("record")}</button></div></div>
        <div className="timeline">{stageHistory.map((e) => <div className="timeline-row" key={e.id}><i/><div><b>{localeLabel(locale, e.to_stage)}</b><span>{displayDate(e.changed_at)} · {e.changed_by_name || ""}</span></div></div>)}</div></section>
      <section className="modal-section"><div className="section-title"><h3>{t("consent")}</h3></div>{h.consents.map((c) => <div className="consent-row" key={c.id}><ShieldCheck size={15}/><div><b>{c.scope} · {c.purpose}</b><span>{t("consent")} {displayDate(c.granted_at)} {c.revoked_at && ` · ${t("consentRevokedAt")} ${displayDate(c.revoked_at)}`}</span></div></div>)}
        {h.disclosures.map((d) => <div className="consent-row" key={d.id}><FileText size={15}/><div><b>{d.scope} → {d.disclosed_to}</b><span>{t("disclosedAt")} {displayDate(d.disclosed_at)}</span></div></div>)}
        <div className="privacy-lock"><ShieldCheck size={15}/>L1 原始診断データは非表示 · 閲覧操作は監査ログに記録されます。</div>
        {["advisor", "manager", "hq_finance", "executive"].includes(role) &&
          <DisclosureForm household={h} t={t} api={api}/>}
        {["advisor", "manager", "hq_finance", "executive"].includes(role) &&
          <DataCorrectionForm household={h} t={t} api={api}/>}
      </section>
    </div><div className="modal-column"><section className="modal-section"><div className="section-title"><h3>{t("negotiations")}</h3><button className="mini-action" onClick={onActivity}><Plus size={13}/>{t("quickActivity")}</button></div>
      {h.introductions.map((intro) => <div className="intro-detail-card" key={intro.id}>
        <div className="negotiation-mini"><div className="partner-icon"><Building2 size={16}/></div><div className="nego-mini-main"><b>{intro.partner_name}</b><span>{intro.staff_name} · {displayDate(intro.introduced_at)}</span><div className="nego-progress">{intro.status === "受付確認済" ? t("received") : localeLabel(locale, intro.status)} / {localeLabel(locale, intro.negotiation_status) || "—"}</div>
          {intro.contract_id && <small>{t("contract")} ¥{Number(intro.contract_amount).toLocaleString()} · {t("actualStart")} {displayDate(intro.actual_start_date)} · {t("confirmStart")} {displayDate(intro.confirmed_start_date)}</small>}</div>
          {intro.existing_customer_flag ? <CustomerDisputeBadge t={t}/> : <button className="text-button compact-link" onClick={() => setDisputeIntro(intro.id)}>{t("customerDisputeAction")}</button>}</div>
        <ReferralDocumentPanel introductionId={intro.id} t={t} api={api}/>
      </div>)}
      {!h.introductions.length && <div className="empty-state">{t("noRows")}</div>}
      {disputeIntro && <DisputeForm introId={disputeIntro} t={t} api={api} onCancel={() => setDisputeIntro(null)}/>}
      </section>
      <section className="modal-section"><div className="section-title"><h3>{t("activitiesHistory")}</h3><button className="mini-action" onClick={onActivity}><Plus size={13}/>{t("addActivity")}</button></div>
        {h.activities.slice(0, 6).map((a) => <div className="activity-row" key={a.id}><div className="activity-dot"><Activity size={13}/></div><div><b>{a.type} · {a.user_name}</b><span>{displayDate(a.acted_at)}</span><p>{a.body}</p>{a.next_action && <small>{t("nextAction")}: {a.next_action} · {displayDate(a.next_action_due)}</small>}</div></div>)}</section>
      <section className="modal-section touch-list"><div className="section-title"><h3>{t("touchHistory")}</h3></div>{h.touches.map((touch) => <div key={touch.id}><span>{displayDate(touch.touch_at)}</span><b>{touch.channel}</b><small>{touch.campaign_id || "—"} · {touch.capture_method}</small></div>)}</section>
    </div></div>
  </Modal>;
}
function ReferralDocumentPanel({ introductionId, t, api }) {
  const [documents, setDocuments] = useState([]);
  const [generations, setGenerations] = useState([]);
  const [consent, setConsent] = useState(null);
  const [consentLoaded, setConsentLoaded] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [consentFormOpen, setConsentFormOpen] = useState(false);
  const [consentMethod, setConsentMethod] = useState("signed_form");
  const [consentReference, setConsentReference] = useState("");
  const [consentConfirmed, setConsentConfirmed] = useState(false);
  const [revokeReason, setRevokeReason] = useState("");
  const consentMethodLabel = {
    signed_form: t("signedForm"), web_form: t("webForm"), recorded_call: t("recordedCall"),
  };
  useEffect(() => {
    let active = true;
    fetch(`${API_BASE}/api/introductions/${introductionId}/referral-documents`, { credentials: "include" })
      .then(async (response) => {
        if (!response.ok) throw new Error(t("referralDocumentFailed"));
        return response.json();
      })
      .then((result) => {
        if (active) {
          setDocuments(result.documents || []);
          setGenerations(result.generations || []);
          setConsent(result.consent || null);
          setConsentLoaded(true);
        }
      })
      .catch(() => { if (active) setError(t("referralDocumentFailed")); });
    return () => { active = false; };
  }, [introductionId, refresh]);
  async function generate() {
    setLoading(true);
    setError("");
    try {
      await api(`/api/introductions/${introductionId}/referral-documents`, "POST");
      setRefresh((value) => value + 1);
    } catch (requestError) {
      const message = requestError.message || "";
      setError(message.includes("同意") ? t("referralConsentRequired") : t("referralDocumentFailed"));
    } finally { setLoading(false); }
  }
  async function saveConsent(event) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      await api(`/api/introductions/${introductionId}/referral-consent`, "POST", {
        method: consentMethod, evidence_reference: consentReference, confirmed: consentConfirmed,
      });
      setConsentFormOpen(false);
      setConsentReference("");
      setConsentConfirmed(false);
      setRefresh((value) => value + 1);
    } catch { setError(t("referralConsentRequired")); }
    finally { setLoading(false); }
  }
  async function revokeConsent(event) {
    event.preventDefault();
    if (!consent?.id) return;
    setLoading(true);
    setError("");
    try {
      await api(`/api/consents/${consent.id}/revoke`, "POST", { reason: revokeReason });
      setRevokeReason("");
      setRefresh((value) => value + 1);
    } catch { setError(t("referralDocumentFailed")); }
    finally { setLoading(false); }
  }
  return <div className="referral-documents">
    <div className="referral-documents-heading"><b>{t("referralLetters")}</b>
      <button className="mini-action" onClick={generate} disabled={loading}>
        {loading ? "…" : t("generateReferralLetter")}
      </button>
    </div>
    {consentLoaded && <div className="referral-consent-row">
      {consent?.active
        ? <span>{t("referralConsentActive")} · {consentMethodLabel[consent.consent_method] || consent.consent_method} · {displayDate(consent.expires_at)}</span>
        : <span>{t("referralConsentRequired")}</span>}
      {!consent?.active && <button className="text-button compact-link" onClick={() => setConsentFormOpen((value) => !value)}>{t("recordReferralConsent")}</button>}
    </div>}
    {consentFormOpen && <form className="referral-consent-form" onSubmit={saveConsent}>
      <label>{t("referralConsentMethod")}<select value={consentMethod} onChange={(event) => setConsentMethod(event.target.value)}>
        <option value="signed_form">{t("signedForm")}</option><option value="web_form">{t("webForm")}</option>
        <option value="recorded_call">{t("recordedCall")}</option>
      </select></label>
      <label>{t("consentEvidenceReference")}<input value={consentReference} onChange={(event) => setConsentReference(event.target.value)} minLength={3} maxLength={255} required/></label>
      <label className="referral-consent-check"><input type="checkbox" checked={consentConfirmed} onChange={(event) => setConsentConfirmed(event.target.checked)} required/>{t("consentConfirmed")}</label>
      <button className="mini-action" type="submit" disabled={loading || !consentConfirmed}>{t("record")}</button>
    </form>}
    {consent?.active && <form className="referral-consent-form" onSubmit={revokeConsent}>
      <label>{t("revokeReason")}<input value={revokeReason} onChange={(event) => setRevokeReason(event.target.value)} minLength={5} maxLength={500} required/></label>
      <button className="text-button compact-link" type="submit" disabled={loading || revokeReason.trim().length < 5}>{t("revokeReferralConsent")}</button>
    </form>}
    {error && <small role="alert" className="referral-error">{error}</small>}
    {!documents.length && !generations.length && <small>{t("referralNoDocuments")}</small>}
    {documents.map((document) => <div className="referral-document-row" key={document.id}>
      <span><b>{document.document_number}</b><small>{t("referralExpires")}: {displayDate(document.expires_at)}</small>
        {document.availability_reason && <small>{
          document.availability === "EXPIRED" ? t("referralExpired") :
            document.availability === "CONSENT_INACTIVE" ? t("referralConsentRevoked") : t("referralUnavailable")
        }</small>}
      </span>
      {document.availability === "AVAILABLE" && <>
        <a className="text-button compact-link" href={`${API_BASE}/api/referral-documents/${document.id}/file`} target="_blank" rel="noreferrer">{t("referralPreview")}</a>
        <a className="text-button compact-link" href={`${API_BASE}/api/referral-documents/${document.id}/file?download=true`}>{t("referralDownload")}</a>
      </>}
    </div>)}
    {generations.filter((item) => item.result !== "SUCCESS").slice(0, 3).map((item) =>
      <small className="referral-error" key={item.id}>
        {item.result === "REJECTED" ? t("referralConsentRequired") : t("referralDocumentFailed")}
      </small>)}
  </div>;
}
function DisclosureForm({ household, t, api }) {
  const partners = [...new Map(household.introductions.map((item) => [item.partner_id, item])).values()];
  const consents = household.consents.filter((item) => !item.revoked_at && ["L2", "L3"].includes(item.scope));
  const [partnerId, setPartnerId] = useState(String(partners[0]?.partner_id || ""));
  const [scope, setScope] = useState(consents[0]?.scope || "L2");
  const matchingConsents = consents.filter((item) => item.scope === scope);
  const [consentId, setConsentId] = useState(String(matchingConsents[0]?.id || ""));
  useEffect(() => { setConsentId(String(matchingConsents[0]?.id || "")); }, [scope, household.consents]);
  async function submit(event) {
    event.preventDefault();
    try {
      await api(`/api/households/${household.id}/disclosures`, "POST", {
        partner_id: Number(partnerId), scope, consent_id: Number(consentId),
      });
    } catch { return; }
  }
  if (!partners.length) return null;
  return <form className="governance-inline-form" onSubmit={submit}>
    <h4>{t("disclosure")}</h4>
    <p>{t("disclosureRecordOnly")}</p>
    <label>{t("discloseTo")}<select value={partnerId} onChange={(event) => setPartnerId(event.target.value)}>
      {partners.map((partner) => <option key={partner.partner_id} value={partner.partner_id}>{partner.partner_name}</option>)}
    </select></label>
    <div className="disclosure-fields">
      <label>{t("disclosureScope")}<select value={scope} onChange={(event) => setScope(event.target.value)}>
        <option value="L2">L2</option><option value="L3">L3</option>
      </select></label>
      <label>{t("shareConsent")}<select value={consentId} onChange={(event) => setConsentId(event.target.value)} required>
        {matchingConsents.map((consent) => <option key={consent.id} value={consent.id}>{consent.scope} · {consent.purpose}</option>)}
      </select></label>
    </div>
    {!matchingConsents.length && <small>{t("noActiveConsent")}</small>}
    <button className="secondary-btn" disabled={!matchingConsents.length || !partnerId}>{t("recordDisclosure")}</button>
  </form>;
}
function DataCorrectionForm({ household, t, api }) {
  const [field, setField] = useState("representative_name");
  const [value, setValue] = useState(household.representative_name || "");
  const [reason, setReason] = useState("");
  const fieldLabels = {
    representative_name: t("correctionRepresentative"), area_pref: t("correctionArea"),
    budget_band: t("correctionBudget"), land_status: t("correctionLand"),
  };
  function changeField(nextField) {
    setField(nextField);
    setValue(household[nextField] || "");
  }
  async function submit(event) {
    event.preventDefault();
    try {
      await api(`/api/households/${household.id}/data-corrections`, "POST", {
        field_name: field, requested_value: value, reason,
      });
      setReason("");
    } catch { return; }
  }
  return <form className="governance-inline-form" onSubmit={submit}>
    <h4>{t("requestCorrection")}</h4>
    <div className="disclosure-fields"><label>{t("correctionField")}<select value={field} onChange={(event) => changeField(event.target.value)}>
      {Object.entries(fieldLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
    </select></label>
      {field === "land_status" ? <label>{t("correctionValue")}<select value={value} onChange={(event) => setValue(event.target.value)}>
        {[["有", t("landYes")], ["無", t("landNo")], ["検討中", t("landConsidering")]].map(([item, label]) =>
          <option key={item} value={item}>{label}</option>)}
      </select></label> : <label>{t("correctionValue")}<input value={value} onChange={(event) => setValue(event.target.value)}/></label>}
    </div>
    <label>{t("correctionReason")}<input value={reason} onChange={(event) => setReason(event.target.value)} maxLength={500}/></label>
    <button className="secondary-btn" disabled={!value.trim() || reason.trim().length < 10}>{t("requestCorrection")}</button>
  </form>;
}
function DisputeForm({ introId, t, api, onCancel }) {
  const [reason, setReason] = useState("");
  const [level, setLevel] = useState("B");
  return <div className="dispute-form"><label className="field-label">争議理由<input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="住宅会社から既存顧客の申立て"/></label>
    <label className="field-label">証拠レベル<select value={level} onChange={(e) => setLevel(e.target.value)}><option value="A">A 契約 + 原始紹介記録</option><option value="B">B 住宅会社 CRM</option><option value="C">C 予約・来電記録</option><option value="D">D 口頭</option></select></label>
    <div className="form-actions"><button className="secondary-btn" onClick={onCancel}>{t("cancel")}</button><button className="danger-btn" disabled={!reason.trim()} onClick={() => api(`/api/introductions/${introId}/dispute`, "POST", { reason, evidence_level: level })}>{t("disputed")}</button></div></div>;
}
function Fact({ label, value }) { return <div className="fact-card"><span>{label}</span><b>{value || "—"}</b></div>; }
function ActivityModal({ households, initialHouseholdId, t, onClose, onSubmit }) {
  const [householdId, setHouseholdId] = useState(initialHouseholdId || households[0]?.id || "");
  const [type, setType] = useState("面談");
  const [body, setBody] = useState("");
  const [nextAction, setNextAction] = useState("");
  const [due, setDue] = useState("");
  const [error, setError] = useState("");
  async function submit(event) {
    event.preventDefault();
    setError("");
    try {
      await onSubmit({ household_id: Number(householdId), type, body, next_action: nextAction || null, next_action_due: due || null });
      onClose();
    } catch (submitError) { setError(submitError.message || t("error")); }
  }
  return <Modal onClose={onClose} label={t("addActivity")} closeLabel={t("close")}
    heading={<div><div className="eyebrow">{t("activityLog")}</div><h2>{t("addActivity")}</h2></div>}>
    <form onSubmit={submit}>
    <label className="field-label">{t("household")}<select value={householdId} onChange={(e) => setHouseholdId(e.target.value)}>{households.map((h) => <option key={h.id} value={h.id}>{h.representative_name}</option>)}</select></label>
    <label className="field-label">{t("activityType")}<select value={type} onChange={(e) => setType(e.target.value)}>{[["面談","meeting"],["電話","phone"],["LINE","line"],["訪問同行","visit"],["メモ","memo"]].map(([value,key]) => <option key={value} value={value}>{t(key)}</option>)}</select></label>
    <label className="field-label">{t("body")}<textarea required value={body} onChange={(e) => setBody(e.target.value)} rows="3"/></label>
    <label className="field-label">{t("nextAction")}<input value={nextAction} onChange={(e) => setNextAction(e.target.value)}/></label>
    <label className="field-label">{t("nextDue")}<input type="date" value={due} onChange={(e) => setDue(e.target.value)}/></label>
    {error && <p className="config-error" role="alert">{error}</p>}
    <div className="form-actions"><button type="button" className="secondary-btn" onClick={onClose}>{t("cancel")}</button><button className="primary-btn"><Check size={15}/>{t("send")}</button></div>
  </form></Modal>;
}
function IntroductionModal({ household, data, t, onClose, onSubmit }) {
  const [partnerId, setPartnerId] = useState(data.partners[0]?.id || "");
  const staff = data.partner_staff.filter((s) => s.partner_id === Number(partnerId));
  const [staffId, setStaffId] = useState("");
  const [error, setError] = useState("");
  useEffect(() => setStaffId(String(staff[0]?.id || "")), [partnerId]);
  async function submit(event) {
    event.preventDefault();
    setError("");
    try {
      await onSubmit({ household_id: household.id, partner_id: Number(partnerId), partner_staff_id: Number(staffId) });
      onClose();
    } catch (submitError) { setError(submitError.message || t("error")); }
  }
  return <Modal onClose={onClose} label={t("partnerCreate")} closeLabel={t("close")}
    heading={<div><div className="eyebrow">{t("partnerIntroduction")}</div><h2>{t("partnerCreate")}</h2><p>{household.representative_name}</p></div>}>
    <form onSubmit={submit}>
    <label className="field-label">{t("partnerSelect")}<select value={partnerId} onChange={(e) => setPartnerId(e.target.value)}>{data.partners.map((p) => <option key={p.id} value={p.id}>{p.name} · {p.area}</option>)}</select></label>
    <label className="field-label">{t("staffSelect")}<select value={staffId} onChange={(e) => setStaffId(e.target.value)}>{staff.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
    <div className="privacy-lock"><ShieldCheck size={15}/>顧客への情報共有は同意された範囲に限定されます。</div>
    {error && <p className="config-error" role="alert">{error}</p>}
    <div className="form-actions"><button type="button" className="secondary-btn" onClick={onClose}>{t("cancel")}</button><button className="primary-btn"><Plus size={15}/>{t("add")}</button></div>
  </form></Modal>;
}
function Modal({ children, heading, label, closeLabel, onClose, wide }) {
  const closeRef = useRef(null);
  useEffect(() => {
    const trigger = document.activeElement;
    closeRef.current?.focus({ preventScroll: true });
    return () => trigger?.focus({ preventScroll: true });
  }, []);

  function handleKeys(event) {
    if (event.key === "Escape") {
      onClose();
      return;
    }
    if (event.key !== "Tab") return;
    const focusable = [...event.currentTarget.querySelectorAll(
      "a[href], button:not(:disabled), input:not(:disabled):not([type=hidden]), select:not(:disabled), textarea:not(:disabled), summary"
    )].filter((element) => element.getClientRects().length);
    const first = focusable[0];
    const last = focusable.at(-1);
    if (event.shiftKey && event.target === first) {
      event.preventDefault();
      last?.focus();
    } else if (!event.shiftKey && event.target === last) {
      event.preventDefault();
      first?.focus();
    }
  }
  return <div className="modal-backdrop" onMouseDown={(event) => {
    if (event.target === event.currentTarget) onClose();
  }}>
    <div className={`modal${wide ? " modal-wide" : ""}`} role="dialog" aria-modal="true" aria-label={label} onKeyDown={handleKeys}>
      <div className={`modal-heading${wide ? " household-modal-heading" : ""}`}>
        {heading}
        <button ref={closeRef} type="button" className="icon-btn" aria-label={closeLabel} onClick={onClose}><X size={18}/></button>
      </div>
      <div className="modal-body">{children}</div>
    </div>
  </div>;
}

createRoot(document.getElementById("root")).render(<App/>);
