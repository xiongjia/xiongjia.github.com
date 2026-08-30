/**
 * Demo queues. One job type = one queue; the queue name is the job type name.
 */

export const QUEUES = {
  ECHO: "echo",
  FLAKY: "flaky",
  SLOW: "slow",
} as const;

export type QueueName = (typeof QUEUES)[keyof typeof QUEUES];

export const REGISTERED_QUEUES: readonly QueueName[] = [
  QUEUES.ECHO,
  QUEUES.FLAKY,
  QUEUES.SLOW,
];

export function isRegisteredQueue(value: string): value is QueueName {
  return REGISTERED_QUEUES.includes(value as QueueName);
}
