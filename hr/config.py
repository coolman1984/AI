"""HR customizing (Egypt).

The legal rates below are the defaults delivered with NERP; they are stored in
the table hr_config and can be changed in transaction ZHR_CONF. CONFIRM THEM WITH
THE COMPANY'S PAYROLL / TAX ADVISER BEFORE GO-LIVE - laws and ceilings change.

Social insurance (law 148/2019): employee 11 %, employer 18.75 % of the insurable
wage, limited by a minimum and a maximum insurable wage per month.
Salary income tax (law 7/2023 as delivered): annual brackets on (gross - employee
social insurance) x 12 minus the personal exemption; monthly tax = annual / 12.
Martyrs' fund: 0.05 % of the gross salary.
Overtime (labour law): +35 % day, +70 % night, +100 % rest day / holiday on the
hourly rate (basic / 30 / 8).
Annual leave: 21 days, 30 days from 10 years of service or age 50; casual leave
6 days (part of the annual quota).
"""

DEFAULTS = {
    "si_ee_pct": "1100",          # basis points
    "si_er_pct": "1875",
    "si_min": "230000",           # cents per month (insurable wage)
    "si_max": "1450000",
    "tax_exemption": "2000000",   # cents per year
    "tax_brackets": "4000000:0,5500000:1000,7000000:1500,20000000:2000,40000000:2250,120000000:2500,999999999999:2750",
    "martyrs_pct": "5",           # basis points (0.05 %)
    "ot_day_pct": "13500",        # basis points of the hourly rate
    "ot_night_pct": "17000",
    "ot_rest_pct": "20000",
    "leave_days": "21",
    "leave_days_senior": "30",
    "casual_days": "6",
    "hours_per_day": "8",
    "days_per_month": "30",
}
CONFIG_TEXT = {
    "si_ee_pct": "Social insurance - employee share (basis points, 1100 = 11 %)",
    "si_er_pct": "Social insurance - employer share (basis points, 1875 = 18.75 %)",
    "si_min": "Minimum insurable wage per month (EGP x 100)",
    "si_max": "Maximum insurable wage per month (EGP x 100)",
    "tax_exemption": "Personal tax exemption per year (EGP x 100)",
    "tax_brackets": "Annual tax brackets: upper limit (EGP x 100) : rate (basis points), ...",
    "martyrs_pct": "Martyrs' fund (basis points of gross, 5 = 0.05 %)",
    "ot_day_pct": "Overtime day (basis points of hourly rate, 13500 = 135 %)",
    "ot_night_pct": "Overtime night (basis points of hourly rate)",
    "ot_rest_pct": "Overtime rest day / holiday (basis points of hourly rate)",
    "leave_days": "Annual leave days",
    "leave_days_senior": "Annual leave days from 10 years of service or age 50",
    "casual_days": "Casual leave days (part of the annual quota)",
    "hours_per_day": "Working hours per day",
    "days_per_month": "Days per month for day / hourly rates",
}

# absence types (T554S): paid?, counts against the annual quota?
ABSENCE_TYPES = {
    "ANN": dict(text="Annual leave", paid=True, quota="ANN"),
    "CAS": dict(text="Casual leave", paid=True, quota="ANN"),
    "SIC": dict(text="Sick leave (medical certificate)", paid=True, quota=None),
    "UNP": dict(text="Unpaid leave", paid=False, quota=None),
    "ABS": dict(text="Unexcused absence", paid=False, quota=None),
    "MAT": dict(text="Maternity leave", paid=True, quota=None),
    "HAJ": dict(text="Hajj leave (once)", paid=True, quota=None),
}
OVERTIME_TYPES = {"D": "Overtime - day", "N": "Overtime - night", "R": "Overtime - rest day / holiday"}

EMPLOYEE_GROUPS = {"1": "Permanent", "2": "Fixed-term contract", "3": "Trainee"}
EMPLOYEE_SUBGROUPS = {"W": "Worker (hourly paid)", "S": "Staff", "M": "Management"}
ACTIONS = {"01": "Hiring", "02": "Organizational change", "03": "Pay change", "10": "Leaving"}
LEAVE_REASONS = {"01": "Resignation", "02": "End of contract", "03": "Dismissal", "04": "Retirement", "05": "Death"}

# payroll accounts (company code 1000)
ACCOUNTS = dict(salaries="430000", wages="420000", employer_si="440000", payable="176000",
                si_payable="178000", tax_payable="178100", martyrs_payable="178200", bank="113100")
