# Data checks: /Users/woojinji/IAA/data

## 1. Schema
Perils: {'buildings': ['accidental_damage', 'escape_of_water', 'fire', 'flood', 'storm', 'subsidence'], 'contents': ['accidental_damage', 'escape_of_water', 'flood', 'theft'], 'motor': ['bodily_injury', 'glass_hail', 'own_damage', 'theft', 'third_party_prop']}. Statuses: ['closed', 'open', 'repudiated'].
```
                               rows  columns
addresses.parquet            575983       16
claims.parquet               163150       12
customers.parquet            545240       18
policies_buildings.parquet   707726       27
policies_contents.parquet    721617       28
policies_motor.parquet       979968       39
sample_submission.parquet    626639        2
test_buildings.parquet       184155       26
test_contents.parquet        187498       27
test_motor.parquet           254986       38
weather.parquet             2879915        9
```

## 2. Data quality
Valuation date (last report date): 2024-12-30.
```
line                                    motor  buildings   contents
train rows                             979968     707726     721617
test rows                              254986     184155     187498
years                               2021-2024  2021-2024  2021-2024
exposure not consistent with dates      0.57%      0.58%      0.58%
test exposure not consistent            0.00%      0.00%      0.00%
claims                                 112606      26442      24102
duplicates                                411        109         84
repudiated                              1.25%      0.00%      1.24%
outside any period                      0.26%      0.25%      0.21%
report before loss                          0          0          0
negative amounts                            0          0          0
closed with paid != incurred            0.00%      0.00%      0.00%
open share                              6.63%      7.18%      3.37%
```

## 2b. Missing values (top columns)

```
        line             column missing (train) missing (test)
0      motor   telematics_score           87.6%          86.7%
1      motor     annual_mileage            2.5%           2.5%
2      motor     engine_size_cc            2.5%           2.5%
3      motor        vehicle_age            2.5%           2.5%
4      motor  overnight_parking            2.5%           2.5%
5  buildings       smoke_alarms            2.5%           2.5%
6  buildings    days_unoccupied            2.5%           2.5%
7   contents   high_value_items            2.5%           2.5%
8   contents     security_level            2.5%           2.5%
```

## 3. Completeness by peril and year — motor
ref_year: lag pattern of the first year; lynden_bell: all years, truncation-corrected.
```
                 ref_year                      lynden_bell                     
year                 2021   2022   2023   2024        2021   2022   2023   2024
peril                                                                          
bodily_injury       0.999  0.993  0.942  0.560       0.998  0.991  0.941  0.562
glass_hail          1.000  1.000  0.998  0.970       1.000  1.000  0.998  0.971
own_damage          1.000  1.000  0.999  0.965       1.000  1.000  0.999  0.965
theft               1.000  1.000  0.998  0.977       1.000  1.000  0.999  0.979
third_party_prop    1.000  1.000  0.998  0.935       1.000  1.000  0.999  0.937
```

## 4. Reporting speed (claims reported within 365 days) — motor

```
               peril loss half     n    30d    90d   180d
0      bodily_injury    2021H1   862  0.175  0.443  0.725
1      bodily_injury    2021H2   980  0.167  0.445  0.728
2      bodily_injury    2022H1   898  0.196  0.449  0.714
3      bodily_injury    2022H2   963  0.184  0.469  0.745
4      bodily_injury    2023H1   921  0.178  0.466  0.717
5      bodily_injury    2023H2   958  0.176  0.443  0.728
6         glass_hail    2021H1  1684  0.988  1.000  1.000
7         glass_hail    2021H2  1865  0.988  1.000  1.000
8         glass_hail    2022H1  1913  0.988  1.000  1.000
9         glass_hail    2022H2  2004  0.987  1.000  1.000
10        glass_hail    2023H1  1918  0.987  1.000  1.000
11        glass_hail    2023H2  2179  0.984  1.000  1.000
12        own_damage    2021H1  5623  0.949  1.000  1.000
13        own_damage    2021H2  6311  0.954  1.000  1.000
14        own_damage    2022H1  6329  0.953  1.000  1.000
15        own_damage    2022H2  6503  0.945  1.000  1.000
16        own_damage    2023H1  5751  0.950  1.000  1.000
17        own_damage    2023H2  6095  0.954  1.000  1.000
18             theft    2021H1   715  0.996  1.000  1.000
19             theft    2021H2   756  0.997  1.000  1.000
20             theft    2022H1   775  0.996  1.000  1.000
21             theft    2022H2   758  0.999  1.000  1.000
22             theft    2023H1   803  0.999  1.000  1.000
23             theft    2023H2   794  0.999  1.000  1.000
24  third_party_prop    2021H1  3814  0.772  0.987  1.000
25  third_party_prop    2021H2  4329  0.767  0.988  1.000
26  third_party_prop    2022H1  4239  0.785  0.991  1.000
27  third_party_prop    2022H2  4525  0.776  0.987  1.000
28  third_party_prop    2023H1  4068  0.776  0.986  1.000
29  third_party_prop    2023H2  4271  0.774  0.990  0.999
```

## 3. Completeness by peril and year — buildings
ref_year: lag pattern of the first year; lynden_bell: all years, truncation-corrected.
```
                  ref_year                    lynden_bell                   
year                  2021 2022   2023   2024        2021 2022   2023   2024
peril                                                                       
accidental_damage      1.0  1.0  0.998  0.965         1.0  1.0  0.999  0.966
escape_of_water        1.0  1.0  0.999  0.951         1.0  1.0  0.999  0.951
fire                   1.0  1.0  0.998  0.980         1.0  1.0  0.999  0.980
flood                  1.0  1.0  0.999  0.965         1.0  1.0  0.999  0.964
storm                  1.0  1.0  0.999  0.964         1.0  1.0  0.998  0.963
subsidence             1.0  1.0  0.993  0.688         1.0  1.0  0.982  0.662
```

## 4. Reporting speed (claims reported within 365 days) — buildings

```
                peril loss half     n    30d    90d   180d
0   accidental_damage    2021H1   391  0.951  1.000  1.000
1   accidental_damage    2021H2   479  0.960  1.000  1.000
2   accidental_damage    2022H1   490  0.945  1.000  1.000
3   accidental_damage    2022H2   502  0.964  1.000  1.000
4   accidental_damage    2023H1   464  0.959  1.000  1.000
5   accidental_damage    2023H2   502  0.944  1.000  1.000
6     escape_of_water    2021H1  1242  0.862  0.998  1.000
7     escape_of_water    2021H2  1225  0.869  0.998  1.000
8     escape_of_water    2022H1  1283  0.863  0.997  1.000
9     escape_of_water    2022H2  1224  0.883  0.997  1.000
10    escape_of_water    2023H1  1285  0.861  0.998  1.000
11    escape_of_water    2023H2  1219  0.875  0.998  1.000
12               fire    2021H1   125  0.984  1.000  1.000
13               fire    2021H2   110  1.000  1.000  1.000
14               fire    2022H1   145  1.000  1.000  1.000
15               fire    2022H2   137  1.000  1.000  1.000
16               fire    2023H1   133  1.000  1.000  1.000
17               fire    2023H2   146  1.000  1.000  1.000
18              flood    2021H1   260  0.965  1.000  1.000
19              flood    2021H2   292  0.966  1.000  1.000
20              flood    2022H1   279  0.943  1.000  1.000
21              flood    2022H2   304  0.934  1.000  1.000
22              flood    2023H1   259  0.938  1.000  1.000
23              flood    2023H2   289  0.948  1.000  1.000
24              storm    2021H1   892  0.941  1.000  1.000
25              storm    2021H2   874  0.946  1.000  1.000
26              storm    2022H1   988  0.942  0.998  1.000
27              storm    2022H2   966  0.946  1.000  1.000
28              storm    2023H1  1001  0.953  1.000  1.000
29              storm    2023H2  1120  0.947  1.000  1.000
30         subsidence    2021H1   143  0.203  0.490  0.776
31         subsidence    2021H2   131  0.298  0.565  0.840
32         subsidence    2022H1   157  0.185  0.465  0.758
33         subsidence    2022H2   155  0.194  0.548  0.819
34         subsidence    2023H1   187  0.171  0.497  0.786
35         subsidence    2023H2   175  0.280  0.554  0.777
```

## 3. Completeness by peril and year — contents
ref_year: lag pattern of the first year; lynden_bell: all years, truncation-corrected.
```
                  ref_year                    lynden_bell                   
year                  2021 2022   2023   2024        2021 2022   2023   2024
peril                                                                       
accidental_damage      1.0  1.0  0.999  0.964         1.0  1.0  0.999  0.964
escape_of_water        1.0  1.0  0.997  0.948         1.0  1.0  0.998  0.950
flood                  1.0  1.0  0.995  0.951         1.0  1.0  0.998  0.960
theft                  1.0  1.0  0.999  0.979         1.0  1.0  0.999  0.979
```

## 4. Reporting speed (claims reported within 365 days) — contents

```
                peril loss half     n    30d    90d  180d
0   accidental_damage    2021H1  1026  0.948  1.000   1.0
1   accidental_damage    2021H2  1132  0.952  0.999   1.0
2   accidental_damage    2022H1  1084  0.943  1.000   1.0
3   accidental_damage    2022H2  1146  0.952  1.000   1.0
4   accidental_damage    2023H1  1159  0.949  1.000   1.0
5   accidental_damage    2023H2  1198  0.945  1.000   1.0
6     escape_of_water    2021H1   631  0.916  0.997   1.0
7     escape_of_water    2021H2   627  0.855  0.998   1.0
8     escape_of_water    2022H1   710  0.872  0.999   1.0
9     escape_of_water    2022H2   648  0.867  0.998   1.0
10    escape_of_water    2023H1   729  0.866  0.993   1.0
11    escape_of_water    2023H2   641  0.847  0.991   1.0
12              flood    2021H1   206  0.947  1.000   1.0
13              flood    2021H2   191  0.948  0.995   1.0
14              flood    2022H1   198  0.949  1.000   1.0
15              flood    2022H2   203  0.946  1.000   1.0
16              flood    2023H1   194  0.938  1.000   1.0
17              flood    2023H2   252  0.937  1.000   1.0
18              theft    2021H1   832  0.996  1.000   1.0
19              theft    2021H2   904  0.998  1.000   1.0
20              theft    2022H1   914  0.998  1.000   1.0
21              theft    2022H2  1018  0.999  1.000   1.0
22              theft    2023H1   995  0.999  1.000   1.0
23              theft    2023H2   969  1.000  1.000   1.0
```

## 5. Step scan, claims (quarterly) — flagged
3 of 75 series. Loss date = law or environment; report date = handling or reserving; policy start = product. Full table: step_scan_claims.csv.
```
     line             peril            measure      basis   break   step  trend_pa    dbic
10  motor        own_damage          frequency  loss date  2023Q1  0.918     0.005  20.702
20  motor  third_party_prop          frequency  loss date  2022Q1  1.059    -0.044  17.185
4   motor     bodily_injury  severity (closed)  loss date  2023Q1  0.784     0.031  16.305
```

## 6. Policy scan (monthly, month-of-year effects) — flagged
15 of 119 series. Full table: step_scan_policies.csv.
```
         line                            series    break   step  trend_pa    dbic
59      motor             mean premium_per_year  2021-06  1.509     0.053  57.391
30   contents             mean premium_per_year  2021-05  1.600     0.088  55.942
27  buildings             mean premium_per_year  2021-05  1.576     0.069  51.201
54      motor    share renewal_decision=renewed  2021-05  0.897    -0.008  50.369
26   contents    share renewal_decision=renewed  2021-04  0.896    -0.008  45.660
23  buildings    share renewal_decision=renewed  2021-04  0.905    -0.005  38.830
48      motor                share new_business  2022-01  1.121     0.002  32.696
20   contents                share new_business  2022-01  1.113    -0.003  20.562
2       motor                    mean ncb_years  2021-04  1.050     0.024  18.894
49      motor                mean renewal_count  2022-01  0.856    -0.054  18.204
21   contents                mean renewal_count  2022-01  0.838    -0.045  17.032
51      motor             mean discount_applied  2022-01  1.048     0.001  16.656
17      motor          share vehicle_colour=red  2022-12  0.911     0.038  16.221
18  buildings                mean renewal_count  2022-01  0.820    -0.041  12.332
31      motor  share overnight_parking=driveway  2021-06  1.033    -0.009  12.129
```

## 7. Leakage suspects
Same-year correlation >= 2x next-year (and >= 0.05), or test mean > 20% from the last training year. Full table: leakage.csv.
```
         line                     column  corr same year  corr next year   ratio  mean 2024  mean test  test / last year
15      motor  customer_service_contacts           0.561           0.047  12.006      0.671      0.401             0.597
9   buildings  customer_service_contacts           0.352           0.007  51.993      0.503      0.402             0.799
9    contents  customer_service_contacts           0.334           0.005  62.573      0.488      0.401             0.821
```
