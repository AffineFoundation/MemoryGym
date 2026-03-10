# MemoryGym Leaderboard

## Overall Rankings

| Rank | Model                                    | Avg Score | Evals | Templates              |
| ---- | ---------------------------------------- | --------- | ----- | ---------------------- |
| 1    | Qwen/Qwen3.5-397B-A17B-TEE               |   30.4%   |    12 | city, company, hospital, movie, research, sport |
| 2    | moonshotai/Kimi-K2.5-TEE                 |   27.8%   |    18 | city, company, hospital, movie, research, sport |
| 3    | Qwen/Qwen3-235B-A22B-Instruct-2507-TEE   |   17.9%   |     7 | city, company, hospital, movie, research, sport |
| 4    | MiniMaxAI/MiniMax-M2.5-TEE               |   12.9%   |     7 | city, company, hospital, movie, research, sport |
| 5    | zai-org/GLM-5-TEE                        |    7.5%   |     2 | company, movie         |

## Detailed Results

| Model                                    | Template | Seed | Tier | Score | Retrieval | Update | Traj |
| ---------------------------------------- | -------- | ---- | ---- | ----- | --------- | ------ | ---- |
| moonshotai/Kimi-K2.5-TEE                 | research |    1 | standard |   55% | 33%       | 75%    | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | sport    |    0 | standard |   45% | 22%       | 100%   | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | hospital |    0 | standard |   40% | 33%       | 40%    | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | research |    1 | lite |   40% | 25%       | 50%    | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | sport    |    1 | lite |   40% | 0%        | 67%    | yes  |
| moonshotai/Kimi-K2.5-TEE                 | city     |    1 | standard |   40% | 22%       | 67%    | yes  |
| moonshotai/Kimi-K2.5-TEE                 | research |    2 | standard |   40% | 25%       | 75%    | yes  |
| moonshotai/Kimi-K2.5-TEE                 | sport    |    2 | standard |   40% | 38%       | 50%    | yes  |
| Qwen/Qwen3-235B-A22B-Instruct-2507-TEE   | hospital |    0 | standard |   30% | 33%       | 60%    | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | city     |    1 | lite |   30% | 20%       | 100%   | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | company  |    0 | standard |   30% | 22%       | 33%    | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | hospital |    1 | lite |   30% | 0%        | 33%    | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | movie    |    1 | lite |   30% | 20%       | 50%    | yes  |
| moonshotai/Kimi-K2.5-TEE                 | city     |    0 | standard |   30% | 20%       | 100%   | yes  |
| moonshotai/Kimi-K2.5-TEE                 | company  |    2 | hard |   30% | 8%        | 57%    | yes  |
| moonshotai/Kimi-K2.5-TEE                 | hospital |    0 | standard |   30% | 22%       | 20%    | yes  |
| moonshotai/Kimi-K2.5-TEE                 | hospital |    2 | standard |   30% | 0%        | 60%    | yes  |
| moonshotai/Kimi-K2.5-TEE                 | movie    |    0 | standard |   30% | 12%       | 0%     | yes  |
| moonshotai/Kimi-K2.5-TEE                 | movie    |    2 | standard |   30% | 11%       | 100%   | yes  |
| Qwen/Qwen3-235B-A22B-Instruct-2507-TEE   | company  |    0 | standard |   25% | 33%       | 67%    | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | movie    |    0 | standard |   25% | 0%        | 50%    | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | research |    0 | standard |   25% | 0%        | 33%    | yes  |
| moonshotai/Kimi-K2.5-TEE                 | company  |    0 | standard |   25% | 11%       | 33%    | yes  |
| moonshotai/Kimi-K2.5-TEE                 | movie    |    1 | standard |   25% | 12%       | 33%    | yes  |
| moonshotai/Kimi-K2.5-TEE                 | research |    0 | standard |   25% | 0%        | 0%     | yes  |
| MiniMaxAI/MiniMax-M2.5-TEE               | sport    |    0 | standard |   20% | 0%        | 75%    | yes  |
| Qwen/Qwen3-235B-A22B-Instruct-2507-TEE   | research |    0 | standard |   20% | 20%       | 33%    | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | company  |    1 | lite |   20% | 0%        | 50%    | yes  |
| moonshotai/Kimi-K2.5-TEE                 | company  |    1 | hard |   20% | 8%        | 0%     | yes  |
| MiniMaxAI/MiniMax-M2.5-TEE               | city     |    0 | standard |   15% | 0%        | 50%    | yes  |
| MiniMaxAI/MiniMax-M2.5-TEE               | movie    |    0 | standard |   15% | 12%       | 0%     | yes  |
| MiniMaxAI/MiniMax-M2.5-TEE               | research |    0 | standard |   15% | 0%        | 33%    | yes  |
| Qwen/Qwen3-235B-A22B-Instruct-2507-TEE   | city     |    0 | standard |   15% | 10%       | 50%    | yes  |
| Qwen/Qwen3-235B-A22B-Instruct-2507-TEE   | sport    |    0 | standard |   15% | 0%        | 50%    | yes  |
| moonshotai/Kimi-K2.5-TEE                 | sport    |    0 | standard |   15% | 0%        | 25%    | yes  |
| moonshotai/Kimi-K2.5-TEE                 | sport    |    1 | standard |   15% | 12%       | 0%     | yes  |
| MiniMaxAI/MiniMax-M2.5-TEE               | company  |    0 | standard |   10% | 11%       | 33%    | yes  |
| MiniMaxAI/MiniMax-M2.5-TEE               | company  |    1 | lite |   10% | 0%        | 0%     | yes  |
| Qwen/Qwen3-235B-A22B-Instruct-2507-TEE   | company  |    1 | lite |   10% | 0%        | 50%    | yes  |
| Qwen/Qwen3-235B-A22B-Instruct-2507-TEE   | movie    |    0 | standard |   10% | 12%       | 50%    | yes  |
| Qwen/Qwen3.5-397B-A17B-TEE               | city     |    0 | standard |   10% | 0%        | 0%     | yes  |
| moonshotai/Kimi-K2.5-TEE                 | city     |    2 | standard |   10% | 0%        | 0%     | yes  |
| moonshotai/Kimi-K2.5-TEE                 | hospital |    1 | standard |   10% | 0%        | 0%     | yes  |
| zai-org/GLM-5-TEE                        | movie    |    0 | standard |   10% | 0%        | 0%     | yes  |
| MiniMaxAI/MiniMax-M2.5-TEE               | hospital |    0 | standard |    5% | 0%        | 0%     | yes  |
| zai-org/GLM-5-TEE                        | company  |    0 | standard |    5% | 0%        | 0%     | yes  |

*Generated from 46 evaluations across 5 models.*
