# Q36 Conversation context and composer access

Conversation rows now show last activity, unread state and blocked/recoverable status alongside long property titles. Selected conversations retain property context above the transcript and at the composer. An explicit Write a message shortcut scrolls to and focuses the existing composer, including on narrow screens. The measured viewport, foreground polling, history ranges, read acknowledgement and retry/client IDs are unchanged.

Node24 typecheck and 12 message-model tests passed. Isolated browser `q36-messages-20261117` passed 4/4 desktop/mobile cases: long synthetic transcript at 320px, offscreen arrival stays unread and does not change scroll position, explicit composer jump/focus, reduced viewport with draft intact, and the complete real owner/renter messaging/publication journey. The reduced browser viewport is keyboard-layout coverage, not installed native keyboard acceptance.

Independent Terra high review identified a delayed native measurement/focus race. The shortcut now captures target and view identities and checks them before both scroll and frame-delayed focus. Two controlled navigation tests passed (14 focused total). Q37 extends the shared exit guard; installed native keyboard testing remains external.
