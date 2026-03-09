# MemoryGym Leaderboard

## Overall Rankings

| Rank | Model                                    | Avg Score | Evals | Templates              |
| ---- | ---------------------------------------- | --------- | ----- | ---------------------- |
| 1    | Qwen/Qwen2.5-72B-Instruct                |   83.3%   |     1 | company                |
| 2    | Qwen/Qwen3.5-397B-A17B-TEE               |   73.3%   |     3 | city, hospital, research |
| 3    | moonshotai/Kimi-K2.5-TEE                 |   39.0%   |    10 | city, company, hospital, movie, research, sport |
| 4    | Qwen/Qwen3-32B                           |   33.3%   |     3 | company                |
| 5    | MiniMaxAI/MiniMax-M2.5-TEE               |   26.7%   |     6 | city, company, hospital, research, sport |
| 6    | Qwen/Qwen3-235B-A22B-Instruct-2507-TEE   |   25.0%   |     4 | company                |
| 7    | Qwen/Qwen3-14B                           |   20.0%   |     1 | company                |
| 8    | openai/gpt-oss-120b-TEE                  |    0.0%   |     1 | company                |

## Detailed Results

| Model                                    | Template | Seed | Tier | Score | Retrieval | Update | Traj |
| ---------------------------------------- | -------- | ---- | ---- | ----- | --------- | ------ | ---- |
| Qwen/Qwen3.5-397B-A17B-TEE               | hospital |    1 | lite |   90% | 100%      | 100%   |      |
| Qwen/Qwen2.5-72B-Instruct                | company  |    0 | lite |   83% | 100%      | 100%   |      |
| Qwen/Qwen3.5-397B-A17B-TEE               | research |    1 | lite |   70% | 100%      | 33%    |      |
| Qwen/Qwen3.5-397B-A17B-TEE               | city     |    1 | lite |   60% | 100%      | 33%    |      |
| moonshotai/Kimi-K2.5-TEE                 | movie    |    0 | standard |   55% | 56%       | 25%    | yes  |
| MiniMaxAI/MiniMax-M2.5-TEE               | company  |    1 | lite |   50% | 50%       | 67%    |      |
| MiniMaxAI/MiniMax-M2.5-TEE               | hospital |    0 | lite |   50% | 40%       | 50%    | yes  |
| Qwen/Qwen3-235B-A22B-Instruct-2507-TEE   | company  |    1 | lite |   50% | 75%       | 33%    |      |
| moonshotai/Kimi-K2.5-TEE                 | company  |    1 | lite |   50% | 75%       | 33%    |      |
| Qwen/Qwen3-32B                           | company  |    2 | standard |   45% | 56%       | 0%     |      |
| moonshotai/Kimi-K2.5-TEE                 | company  |    0 | standard |   45% | 67%       | 33%    | yes  |
| moonshotai/Kimi-K2.5-TEE                 | company  |   42 | lite |   40% | 50%       | 0%     | yes  |
| moonshotai/Kimi-K2.5-TEE                 | hospital |    0 | lite |   40% | 40%       | 50%    | yes  |
| moonshotai/Kimi-K2.5-TEE                 | research |    0 | lite |   40% | 60%       | 0%     | yes  |
| moonshotai/Kimi-K2.5-TEE                 | sport    |    1 | standard |   40% | 12%       | 33%    | yes  |
| Qwen/Qwen3-235B-A22B-Instruct-2507-TEE   | company  |    2 | lite |   30% | 20%       | 100%   |      |
| Qwen/Qwen3-32B                           | company  |    1 | lite |   30% | 25%       | 33%    |      |
| moonshotai/Kimi-K2.5-TEE                 | city     |    0 | lite |   30% | 20%       | 0%     | yes  |
| moonshotai/Kimi-K2.5-TEE                 | sport    |    0 | lite |   30% | 40%       | 0%     | yes  |
| Qwen/Qwen3-32B                           | company  |    0 | standard |   25% | 40%       | 0%     |      |
| MiniMaxAI/MiniMax-M2.5-TEE               | city     |    0 | lite |   20% | 0%        | 0%     | yes  |
| MiniMaxAI/MiniMax-M2.5-TEE               | company  |    0 | lite |   20% | 25%       | 0%     | yes  |
| Qwen/Qwen3-14B                           | company  |    1 | lite |   20% | 0%        | 33%    |      |
| moonshotai/Kimi-K2.5-TEE                 | company  |    2 | lite |   20% | 20%       | 0%     | yes  |
| MiniMaxAI/MiniMax-M2.5-TEE               | research |    0 | lite |   10% | 20%       | 0%     | yes  |
| MiniMaxAI/MiniMax-M2.5-TEE               | sport    |    0 | lite |   10% | 0%        | 0%     | yes  |
| Qwen/Qwen3-235B-A22B-Instruct-2507-TEE   | company  |    0 | standard |   10% | 20%       | 0%     |      |
| Qwen/Qwen3-235B-A22B-Instruct-2507-TEE   | company  |    3 | lite |   10% | 25%       | 0%     |      |
| openai/gpt-oss-120b-TEE                  | company  |    0 | standard |    0% | 0%        | 0%     |      |

*Generated from 29 evaluations across 8 models.*
