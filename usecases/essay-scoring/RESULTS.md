# Essay scoring results

Model `jev-1.13.0`. Eight original essays in `data/essays.json`.

| id | expected | got | raw holistic | thesis | evidence | off_prompt | errors | inbox |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| score6-driverless | 6 | 6 | 5.72 | 0.98 | 0.96 | 0.03 | 0.06 | strong |
| score5-phones | 5 | 6 | 5.53 | 0.97 | 0.94 | 0.05 | 0.06 | strong |
| score4-uniforms | 4 | 5 | 4.66 | 0.97 | 0.93 | 0.02 | 0.06 | strong |
| score3-thin-evidence | 3 | 3 | 3.20 | 0.98 | 0.71 | 0.03 | 0.09 | revise |
| score2-off-and-errors | 2 | 2 | 2.02 | 0.24 | 0.48 | 0.08 | 0.16 | reteach |
| score1-no-claim | 1 | 1 | 1.09 | 0.04 | 0.03 | 0.10 | 0.20 | reteach |
| off-prompt | 1 | 1 | 1.01 | 0.01 | 0.05 | 0.99 | 0.09 | reteach |
| errors-obscure | 2 | 3 | 2.83 | 0.85 | 0.78 | 0.03 | 0.19 | revise |

Exact **5/8**. Adjacent (**within 1**) **8/8**.
