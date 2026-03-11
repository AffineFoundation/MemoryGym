# MemoryGym Leaderboard

## Overall Rankings

| Rank | Model                                    | Composite | Avg Score | Evals | Templates              |
| ---- | ---------------------------------------- | --------- | --------- | ----- | ---------------------- |
| 1    | Qwen/Qwen3-235B-A22B-Instruct-2507-TEE   |   19.0%   |   20.6%   |     9 | city, codebase, company, hospital, movie, research, sport, university |
| 2    | Qwen/Qwen3.5-397B-A17B-TEE               |   17.3%   |   30.5%   |    71 | city, codebase, company, hospital, movie, research, sport, university |
| 3    | moonshotai/Kimi-K2.5-TEE                 |   15.6%   |   27.1%   |    21 | city, codebase, company, hospital, movie, research, sport, university |
| 4    | MiniMaxAI/MiniMax-M2.5-TEE               |   15.2%   |   21.8%   |    11 | city, codebase, company, hospital, movie, research, sport, university |
| 5    | zai-org/GLM-5-TEE                        |   10.2%   |   20.6%   |     9 | city, codebase, company, hospital, movie, research, sport, university |

## Detailed Results

| Model                                    | Template | Seed | Tier | Composite | Breadth | Maint. | Reasoning | Efficiency | Traj |
| ---------------------------------------- | -------- | ---- | ---- | --------- | ------- | ------ | --------- | ---------- | ---- |
| Qwen/Qwen3.5-397B-A17B-TEE               | company  |    9 | standard |   48%     | 60%     | 75%    | 25%       | 27%        | yes  |
| moonshotai/Kimi-K2.5-TEE                 | research |    1 | standard |   42%     | 33%     | 75%    | 33%       | 23%        | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | company  |    8 | standard |   38%     | 20%     | 67%    | 44%       | 23%        | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | company  |    6 | standard |   36%     | 57%     | 33%    | 25%       | 23%        | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | hospital |    7 | standard |   36%     | 50%     | 0%     | 67%       | 20%        | yes  |
| moonshotai/Kimi-K2.5-TEE                 | city     |    1 | standard |   36%     | 22%     | 67%    | 33%       | 20%        | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | company  |    4 | standard |   34%     | 67%     | 0%     | 38%       | 23%        | yes  |
| moonshotai/Kimi-K2.5-TEE                 | research |    2 | standard |   34%     | 25%     | 72%    | 17%       | 20%        | yes  |
| moonshotai/Kimi-K2.5-TEE                 | sport    |    2 | standard |   32%     | 38%     | 50%    | 17%       | 20%        | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | research |    5 | standard |   32%     | 50%     | 25%    | 25%       | 20%        | yes  |
| moonshotai/Kimi-K2.5-TEE                 | movie    |    2 | standard |   31%     | 11%     | 87%    | 14%       | 13%        | yes  |
| MiniMaxAI/MiniMax-M2.5-TEE               | codebase |    0 | standard |   29%     | 40%     | 33%    | 22%       | 17%        | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | sport    |    1 | lite |   29%     | 0%      | 67%    | 33%       | 20%        | yes  |
| Qwen/Qwen3-235B-A22B-Instruct-2507-TEE   | university |    0 | standard |   28%     | 57%     | 0%     | 29%       | 20%        | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | university |    0 | standard |   28%     | 57%     | 0%     | 29%       | 20%        | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | research |    6 | standard |   28%     | 43%     | 33%    | 14%       | 17%        | yes  |
| Qwen/Qwen3-235B-A22B-Instruct-2507-TEE   | company  |    0 | standard |   28%     | 33%     | 58%    | 0%        | 17%        | yes  |
| Qwen/Qwen3-235B-A22B-Instruct-2507-TEE   | hospital |    0 | standard |   28%     | 33%     | 54%    | 0%        | 20%        | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | company  |    3 | standard |   27%     | 57%     | 0%     | 25%       | 20%        | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | university |    4 | standard |   27%     | 29%     | 0%     | 57%       | 20%        | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | hospital |    0 | standard |   25%     | 44%     | 0%     | 33%       | 17%        | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | city     |    4 | standard |   25%     | 22%     | 0%     | 57%       | 20%        | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | city     |    6 | standard |   25%     | 33%     | 0%     | 43%       | 20%        | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | sport    |    7 | standard |   25%     | 33%     | 25%    | 20%       | 17%        | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | company  |    0 | standard |   24%     | 29%     | 0%     | 50%       | 17%        | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | research |    8 | standard |   24%     | 20%     | 50%    | 12%       | 13%        | yes  |
| MiniMaxAI/MiniMax-M2.5-TEE               | university |    0 | standard |   24%     | 57%     | 0%     | 14%       | 17%        | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | city     |    9 | standard |   24%     | 50%     | 0%     | 20%       | 20%        | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | hospital |    1 | standard |   24%     | 43%     | 0%     | 33%       | 13%        | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | city     |    8 | standard |   23%     | 25%     | 0%     | 50%       | 17%        | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | university |    3 | standard |   23%     | 50%     | 0%     | 20%       | 13%        | yes  |
| zai-org/GLM-5-TEE                        | codebase |    0 | standard |   23%     | 20%     | 33%    | 22%       | 13%        | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | research |    0 | standard |   22%     | 43%     | 0%     | 25%       | 17%        | yes  |
| zai-org/GLM-5-TEE                        | hospital |    1 | standard |   22%     | 25%     | 13%    | 33%       | 13%        | yes  |
| MiniMaxAI/MiniMax-M2.5-TEE               | company  |    1 | standard |   21%     | 0%      | 32%    | 43%       | 13%        | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | codebase |    1 | standard |   21%     | 29%     | 0%     | 38%       | 17%        | yes  |
| MiniMaxAI/MiniMax-M2.5-TEE               | sport    |    0 | standard |   21%     | 0%      | 75%    | 0%        | 10%        | yes  |
| moonshotai/Kimi-K2.5-TEE                 | hospital |    0 | standard |   20%     | 56%     | 0%     | 0%        | 17%        | yes  |
| MiniMaxAI/MiniMax-M2.5-TEE               | hospital |    1 | standard |   20%     | 25%     | 36%    | 0%        | 17%        | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | research |    0 | standard |   19%     | 0%      | 33%    | 33%       | 13%        | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | research |    9 | standard |   19%     | 20%     | 0%     | 40%       | 17%        | yes  |
| Qwen/Qwen3-235B-A22B-Instruct-2507-TEE   | research |    0 | standard |   19%     | 20%     | 33%    | 11%       | 10%        | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | research |    2 | standard |   19%     | 33%     | 0%     | 25%       | 13%        | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | movie    |    8 | standard |   19%     | 43%     | 0%     | 12%       | 13%        | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | movie    |    0 | standard |   18%     | 43%     | 0%     | 11%       | 13%        | yes  |
| MiniMaxAI/MiniMax-M2.5-TEE               | city     |    0 | standard |   18%     | 0%      | 50%    | 17%       | 7%         | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | company  |    0 | standard |   18%     | 11%     | 33%    | 17%       | 10%        | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | city     |    3 | standard |   18%     | 22%     | 0%     | 33%       | 13%        | yes  |
| moonshotai/Kimi-K2.5-TEE                 | company  |    2 | hard |   17%     | 8%      | 29%    | 13%       | 23%        | yes  |
| Qwen/Qwen3-235B-A22B-Instruct-2507-TEE   | codebase |    0 | standard |   17%     | 20%     | 0%     | 33%       | 13%        | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | codebase |    0 | standard |   17%     | 20%     | 0%     | 33%       | 13%        | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | hospital |    9 | standard |   17%     | 17%     | 0%     | 40%       | 10%        | yes  |
| moonshotai/Kimi-K2.5-TEE                 | codebase |    0 | standard |   17%     | 20%     | 0%     | 33%       | 13%        | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | university |    2 | standard |   17%     | 33%     | 0%     | 17%       | 13%        | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | sport    |    5 | standard |   17%     | 29%     | 0%     | 25%       | 10%        | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | research |    3 | standard |   16%     | 20%     | 20%    | 12%       | 10%        | yes  |
| zai-org/GLM-5-TEE                        | research |    1 | standard |   16%     | 14%     | 24%    | 14%       | 10%        | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | hospital |    2 | standard |   16%     | 29%     | 0%     | 20%       | 10%        | yes  |
| moonshotai/Kimi-K2.5-TEE                 | sport    |    0 | standard |   16%     | 33%     | 0%     | 14%       | 10%        | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | research |    1 | standard |   15%     | 43%     | 0%     | 0%        | 10%        | yes  |
| Qwen/Qwen3-235B-A22B-Instruct-2507-TEE   | city     |    0 | standard |   15%     | 10%     | 42%    | 0%        | 7%         | yes  |
| moonshotai/Kimi-K2.5-TEE                 | hospital |    2 | standard |   14%     | 0%      | 50%    | 0%        | 10%        | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | movie    |    9 | standard |   14%     | 12%     | 0%     | 33%       | 10%        | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | sport    |    9 | standard |   14%     | 12%     | 0%     | 33%       | 10%        | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | hospital |    6 | standard |   14%     | 14%     | 0%     | 33%       | 7%         | yes  |
| Qwen/Qwen3-235B-A22B-Instruct-2507-TEE   | company  |    1 | lite |   14%     | 0%      | 50%    | 0%        | 7%         | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | research |    7 | standard |   14%     | 0%      | 33%    | 17%       | 7%         | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | sport    |    6 | standard |   14%     | 22%     | 0%     | 20%       | 10%        | yes  |
| zai-org/GLM-5-TEE                        | city     |    0 | standard |   14%     | 25%     | 0%     | 17%       | 10%        | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | company  |    5 | standard |   14%     | 20%     | 0%     | 22%       | 10%        | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | hospital |    4 | standard |   13%     | 14%     | 29%    | 0%        | 10%        | yes  |
| moonshotai/Kimi-K2.5-TEE                 | movie    |    1 | standard |   13%     | 12%     | 33%    | 0%        | 7%         | yes  |
| Qwen/Qwen3-235B-A22B-Instruct-2507-TEE   | movie    |    0 | standard |   13%     | 29%     | 0%     | 11%       | 10%        | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | city     |    1 | standard |   13%     | 38%     | 0%     | 0%        | 10%        | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | company  |    7 | standard |   13%     | 38%     | 0%     | 0%        | 10%        | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | sport    |    0 | standard |   13%     | 17%     | 0%     | 25%       | 10%        | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | sport    |    4 | standard |   13%     | 38%     | 0%     | 0%        | 10%        | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | university |    1 | standard |   13%     | 38%     | 0%     | 0%        | 10%        | yes  |
| moonshotai/Kimi-K2.5-TEE                 | university |    1 | standard |   13%     | 38%     | 0%     | 0%        | 10%        | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | codebase |    2 | standard |   13%     | 20%     | 0%     | 20%       | 10%        | yes  |
| MiniMaxAI/MiniMax-M2.5-TEE               | company  |    0 | standard |   13%     | 11%     | 32%    | 0%        | 7%         | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | hospital |    0 | standard |   12%     | 33%     | 0%     | 0%        | 10%        | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | sport    |    2 | standard |   12%     | 33%     | 0%     | 0%        | 10%        | yes  |
| MiniMaxAI/MiniMax-M2.5-TEE               | research |    0 | standard |   12%     | 0%      | 30%    | 11%       | 7%         | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | hospital |    3 | standard |   11%     | 12%     | 0%     | 25%       | 7%         | yes  |
| moonshotai/Kimi-K2.5-TEE                 | research |    0 | standard |   11%     | 33%     | 0%     | 0%        | 7%         | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | company  |    2 | standard |   10%     | 20%     | 0%     | 11%       | 7%         | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | company  |    1 | standard |   10%     | 17%     | 0%     | 14%       | 7%         | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | hospital |    8 | standard |   10%     | 29%     | 0%     | 0%        | 7%         | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | movie    |    2 | standard |   10%     | 29%     | 0%     | 0%        | 7%         | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | sport    |    8 | standard |   10%     | 29%     | 0%     | 0%        | 7%         | yes  |
| moonshotai/Kimi-K2.5-TEE                 | company  |    0 | standard |   10%     | 14%     | 0%     | 17%       | 7%         | yes  |
| Qwen/Qwen3-235B-A22B-Instruct-2507-TEE   | sport    |    0 | standard |    9%     | 17%     | 0%     | 12%       | 7%         | yes  |
| zai-org/GLM-5-TEE                        | sport    |    0 | standard |    9%     | 17%     | 0%     | 12%       | 7%         | yes  |
| moonshotai/Kimi-K2.5-TEE                 | university |    0 | standard |    9%     | 14%     | 0%     | 14%       | 7%         | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | hospital |    5 | standard |    9%     | 0%      | 0%     | 33%       | 3%         | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | city     |    2 | standard |    9%     | 25%     | 0%     | 0%        | 7%         | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | city     |    5 | standard |    9%     | 25%     | 0%     | 0%        | 7%         | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | movie    |    5 | standard |    9%     | 25%     | 0%     | 0%        | 7%         | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | movie    |    7 | standard |    9%     | 25%     | 0%     | 0%        | 7%         | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | city     |    7 | standard |    8%     | 10%     | 0%     | 17%       | 7%         | yes  |
| zai-org/GLM-5-TEE                        | company  |    1 | standard |    8%     | 0%      | 0%     | 29%       | 7%         | yes  |
| moonshotai/Kimi-K2.5-TEE                 | company  |    1 | hard |    8%     | 8%      | 0%     | 13%       | 10%        | yes  |
| MiniMaxAI/MiniMax-M2.5-TEE               | research |    1 | standard |    5%     | 14%     | 0%     | 0%        | 3%         | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | movie    |    3 | standard |    5%     | 14%     | 0%     | 0%        | 3%         | yes  |
| MiniMaxAI/MiniMax-M2.5-TEE               | movie    |    0 | standard |    4%     | 12%     | 0%     | 0%        | 3%         | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | city     |    0 | standard |    4%     | 12%     | 0%     | 0%        | 3%         | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | movie    |    1 | standard |    4%     | 12%     | 0%     | 0%        | 3%         | yes  |
| moonshotai/Kimi-K2.5-TEE                 | sport    |    1 | standard |    4%     | 12%     | 0%     | 0%        | 3%         | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | research |    4 | standard |    4%     | 0%      | 0%     | 12%       | 3%         | yes  |
| MiniMaxAI/MiniMax-M2.5-TEE               | hospital |    0 | standard |    0%     | 0%      | 0%     | 0%        | 0%         | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | movie    |    4 | standard |    0%     | 0%      | 0%     | 0%        | 0%         | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | movie    |    6 | standard |    0%     | 0%      | 0%     | 0%        | 0%         | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | sport    |    3 | standard |    0%     | 0%      | 0%     | 0%        | 0%         | yes  |
| moonshotai/Kimi-K2.5-TEE                 | city     |    0 | standard |    0%     | 0%      | 0%     | 0%        | 0%         | yes  |
| moonshotai/Kimi-K2.5-TEE                 | city     |    2 | standard |    0%     | 0%      | 0%     | 0%        | 0%         | yes  |
| moonshotai/Kimi-K2.5-TEE                 | hospital |    1 | standard |    0%     | 0%      | 0%     | 0%        | 0%         | yes  |
| moonshotai/Kimi-K2.5-TEE                 | movie    |    0 | standard |    0%     | 0%      | 0%     | 0%        | 0%         | yes  |
| zai-org/GLM-5-TEE                        | company  |    0 | standard |    0%     | 0%      | 0%     | 0%        | 0%         | yes  |
| zai-org/GLM-5-TEE                        | movie    |    0 | standard |    0%     | 0%      | 0%     | 0%        | 0%         | yes  |
| zai-org/GLM-5-TEE                        | university |    0 | standard |    0%     | 0%      | 0%     | 0%        | 0%         | yes  |

*Generated from 121 evaluations across 5 models. Last updated: 2026-03-11 23:21 UTC.*