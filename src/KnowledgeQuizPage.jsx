import { useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';

const quizData = [
	{
		moduleTitle: '1. What Is Car Insurance?',
		questions: [
			{
				questionText: 'What is the primary purpose of car insurance?',
				options: {
					A: 'A. Improve driving skills',
					B: 'B. Protect drivers financially after accidents or losses',
					C: 'C. Reduce fuel costs',
					D: 'D. Increase resale value',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Protect drivers financially after accidents or losses',
				},
			},
			{
				questionText: 'Which best describes car insurance?',
				options: {
					A: 'A. Savings account',
					B: 'B. Legal contract',
					C: 'C. Driving permit',
					D: 'D. Warranty',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Legal contract',
				},
			},
			{
				questionText: 'What does liability insurance cover?',
				options: {
					A: 'A. Your car',
					B: 'B. Injuries and damages you cause to others',
					C: 'C. Maintenance',
					D: 'D. Theft',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Injuries and damages you cause to others',
				},
			},
			{
				questionText: 'Why is car insurance required in most states?',
				options: {
					A: 'A. Ensure cars are new',
					B: 'B. Reduce traffic',
					C: 'C. Ensure drivers can pay for damages',
					D: 'D. Track habits',
				},
				correctAnswer: {
					letter: 'C',
					text: 'C. Ensure drivers can pay for damages',
				},
			},
			{
				questionText: 'Who pays the premium?',
				options: {
					A: 'A. Insurer',
					B: 'B. Government',
					C: 'C. Manufacturer',
					D: 'D. Policyholder',
				},
				correctAnswer: {
					letter: 'D',
					text: 'D. Policyholder',
				},
			},
			{
				questionText: 'Which factor affects insurance cost?',
				options: {
					A: 'A. Favorite color',
					B: 'B. Driving history',
					C: 'C. Shoe size',
					D: 'D. Phone brand',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Driving history',
				},
			},
			{
				questionText: 'What happens if you stop paying premiums?',
				options: {
					A: 'A. Coverage increases',
					B: 'B. Policy canceled',
					C: 'C. Free repairs',
					D: 'D. Nothing',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Policy canceled',
				},
			},
			{
				questionText: 'Car insurance helps cover financial losses.',
				options: {
					A: 'True',
					B: 'False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'True',
					text: 'True',
				},
			},
			{
				questionText: 'Insurance only covers your own vehicle.',
				options: {
					A: 'True',
					B: 'False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'False',
					text: 'False',
				},
			},
			{
				questionText: 'Insurance protects against large unexpected expenses.',
				options: {
					A: 'True',
					B: 'False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'True',
					text: 'True',
				},
			},
		],
	},
	{
		moduleTitle: '2. Understanding Deductibles',
		questions: [
			{
				questionText: 'What is a deductible?',
				options: {
					A: 'A. Monthly payment',
					B: 'B. Amount you pay before insurance covers costs',
					C: 'C. Fee',
					D: 'D. Interest',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Amount you pay before insurance covers costs',
				},
			},
			{
				questionText: 'When do you pay a deductible?',
				options: {
					A: 'A. Buying insurance',
					B: 'B. Filing a claim',
					C: 'C. Before driving',
					D: 'D. Monthly',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Filing a claim',
				},
			},
			{
				questionText: 'Higher deductible usually means:',
				options: {
					A: 'A. Higher premium',
					B: 'B. Lower premium',
					C: 'C. No coverage',
					D: 'D. Free repairs',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Lower premium',
				},
			},
			{
				questionText: '$500 deductible, $2,000 repair — insurance pays:',
				options: {
					A: 'A. $500',
					B: 'B. $1,500',
					C: 'C. $2,000',
					D: 'D. $0',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. $1,500',
				},
			},
			{
				questionText: 'Deductibles usually apply to:',
				options: {
					A: 'A. Liability',
					B: 'B. Collision',
					C: 'C. Medical',
					D: 'D. Roadside',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Collision',
				},
			},
			{
				questionText: 'Who chooses deductible amount?',
				options: {
					A: 'A. Government',
					B: 'B. Insurer',
					C: 'C. Policyholder',
					D: 'D. Mechanic',
				},
				correctAnswer: {
					letter: 'C',
					text: 'C. Policyholder',
				},
			},
			{
				questionText: 'Deductibles help prevent:',
				options: {
					A: 'A. Accidents',
					B: 'B. Fraud/small claims',
					C: 'C. Rate increases',
					D: 'D. Cancellation',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Fraud/small claims',
				},
			},
			{
				questionText: 'Deductibles are paid out of pocket.',
				options: {
					A: 'True',
					B: 'False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'True',
					text: 'True',
				},
			},
			{
				questionText: 'Liability coverage usually has a deductible.',
				options: {
					A: 'True',
					B: 'False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'False',
					text: 'False',
				},
			},
			{
				questionText: 'Higher deductibles can lower premiums.',
				options: {
					A: 'True',
					B: 'False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'True',
					text: 'True',
				},
			},
		],
	},
	{
		moduleTitle: '3. Steps to Take During a Car Accident',
		questions: [
			{
				questionText: 'First thing to check after accident?',
				options: {
					A: 'A. Phone',
					B: 'B. Injuries',
					C: 'C. Policy',
					D: 'D. Damage',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Injuries',
				},
			},
			{
				questionText: 'Who to call if injuries occur?',
				options: {
					A: 'A. Agent',
					B: 'B. Tow truck',
					C: 'C. Emergency services',
					D: 'D. Mechanic',
				},
				correctAnswer: {
					letter: 'C',
					text: 'C. Emergency services',
				},
			},
			{
				questionText: 'What info should be exchanged?',
				options: {
					A: 'A. Social media',
					B: 'B. Insurance/contact info',
					C: 'C. Salary',
					D: 'D. Driving record',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Insurance/contact info',
				},
			},
			{
				questionText: 'Why take photos?',
				options: {
					A: 'A. Social media',
					B: 'B. Document damage',
					C: 'C. DIY estimate',
					D: 'D. Avoid police',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Document damage',
				},
			},
			{
				questionText: 'When contact police?',
				options: {
					A: 'A. Never',
					B: 'B. Minor accidents',
					C: 'C. Injuries/major damage',
					D: 'D. Only asked',
				},
				correctAnswer: {
					letter: 'C',
					text: 'C. Injuries/major damage',
				},
			},
			{
				questionText: 'What should you avoid admitting?',
				options: {
					A: 'A. Name',
					B: 'B. Fault',
					C: 'C. Provider',
					D: 'D. License',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Fault',
				},
			},
			{
				questionText: 'When notify insurer?',
				options: {
					A: 'A. ASAP',
					B: 'B. After repair',
					C: 'C. After court',
					D: 'D. Never',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. ASAP',
				},
			},
			{
				questionText: 'Leaving scene is allowed if damage is minor.',
				options: {
					A: 'True',
					B: 'False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'False',
					text: 'False',
				},
			},
			{
				questionText: 'Photos support claims.',
				options: {
					A: 'True',
					B: 'False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'True',
					text: 'True',
				},
			},
			{
				questionText: 'Staying calm is important.',
				options: {
					A: 'True',
					B: 'False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'True',
					text: 'True',
				},
			},
		],
	},
	{
		moduleTitle: '4. Do’s and Don’ts of Safe Driving',
		questions: [
			{
				questionText: 'Safe driving habit?',
				options: {
					A: 'A. Speeding',
					B: 'B. Seat belts',
					C: 'C. Texting',
					D: 'D. Tailgating',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Seat belts',
				},
			},
			{
				questionText: 'What should NOT be done?',
				options: {
					A: 'A. Focus',
					B: 'B. Use mirrors',
					C: 'C. Text',
					D: 'D. Signal',
				},
				correctAnswer: {
					letter: 'C',
					text: 'C. Text',
				},
			},
			{
				questionText: 'Defensive driving means:',
				options: {
					A: 'A. Aggressive',
					B: 'B. Anticipating hazards',
					C: 'C. Slow always',
					D: 'D. Ignore others',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Anticipating hazards',
				},
			},
			{
				questionText: 'Biggest accident risk?',
				options: {
					A: 'A. Awareness',
					B: 'B. Distracted driving',
					C: 'C. Obeying laws',
					D: 'D. Signals',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Distracted driving',
				},
			},
			{
				questionText: 'Safe distance prevents:',
				options: {
					A: 'A. Tickets',
					B: 'B. Rear-end collisions',
					C: 'C. Flats',
					D: 'D. Theft',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Rear-end collisions',
				},
			},
			{
				questionText: 'When use headlights?',
				options: {
					A: 'A. Night only',
					B: 'B. Low visibility',
					C: 'C. Tunnels',
					D: 'D. Never',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Low visibility',
				},
			},
			{
				questionText: 'Road rage is:',
				options: {
					A: 'A. Safe',
					B: 'B. Encouraged',
					C: 'C. Dangerous',
					D: 'D. Legal',
				},
				correctAnswer: {
					letter: 'C',
					text: 'C. Dangerous',
				},
			},
			{
				questionText: 'Speed limits optional.',
				options: {
					A: 'True',
					B: 'False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'False',
					text: 'False',
				},
			},
			{
				questionText: 'Defensive driving reduces risk.',
				options: {
					A: 'True',
					B: 'False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'True',
					text: 'True',
				},
			},
			{
				questionText: 'Safe driving can lower insurance costs.',
				options: {
					A: 'True',
					B: 'False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'True',
					text: 'True',
				},
			},
		],
	},
	{
		moduleTitle: '5. What Is a Premium?',
		questions: [
			{
				questionText: 'Premium is:',
				options: {
					A: 'A. Repair cost',
					B: 'B. Insurance payment',
					C: 'C. Deductible',
					D: 'D. Fine',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Insurance payment',
				},
			},
			{
				questionText: 'Premiums are paid:',
				options: {
					A: 'A. Once',
					B: 'B. Monthly/annually',
					C: 'C. After accidents',
					D: 'D. Never',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Monthly/annually',
				},
			},
			{
				questionText: 'Who pays premium?',
				options: {
					A: 'A. Insurer',
					B: 'B. Government',
					C: 'C. Policyholder',
					D: 'D. Mechanic',
				},
				correctAnswer: {
					letter: 'C',
					text: 'C. Policyholder',
				},
			},
			{
				questionText: 'Premium cost depends on:',
				options: {
					A: 'A. Driving history',
					B: 'B. Shoe size',
					C: 'C. Color',
					D: 'D. Weather',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. Driving history',
				},
			},
			{
				questionText: 'Missing payments can cause:',
				options: {
					A: 'A. Discounts',
					B: 'B. Cancellation',
					C: 'C. Free coverage',
					D: 'D. Refund',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Cancellation',
				},
			},
			{
				questionText: 'Premiums lower for:',
				options: {
					A: 'A. Risky drivers',
					B: 'B. Safe drivers',
					C: 'C. New drivers',
					D: 'D. Uninsured',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Safe drivers',
				},
			},
			{
				questionText: 'Premiums help insurers:',
				options: {
					A: 'A. Pay claims',
					B: 'B. Ticket drivers',
					C: 'C. Fix roads',
					D: 'D. Sell cars',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. Pay claims',
				},
			},
			{
				questionText: 'Premiums refunded after accidents.',
				options: {
					A: 'True',
					B: 'False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'False',
					text: 'False',
				},
			},
			{
				questionText: 'Premiums vary by driver.',
				options: {
					A: 'True',
					B: 'False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'True',
					text: 'True',
				},
			},
			{
				questionText: 'Premiums required to keep coverage.',
				options: {
					A: 'True',
					B: 'False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'True',
					text: 'True',
				},
			},
		],
	},
	{
		moduleTitle: 'Topic 6: Types of Car Insurance Coverage',
		questions: [
			{
				questionText: 'Which type of insurance is required in most states?',
				options: {
					A: 'A. Collision',
					B: 'B. Comprehensive',
					C: 'C. Liability',
					D: 'D. Gap',
				},
				correctAnswer: {
					letter: 'C',
					text: 'C. Liability',
				},
			},
			{
				questionText: 'Which coverage pays for damage to your car after an accident?',
				options: {
					A: 'A. Liability',
					B: 'B. Collision',
					C: 'C. Medical Payments',
					D: 'D. Rental',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Collision',
				},
			},
			{
				questionText: 'Which coverage protects against theft or vandalism?',
				options: {
					A: 'A. Collision',
					B: 'B. Liability',
					C: 'C. Comprehensive',
					D: 'D. Uninsured Motorist',
				},
				correctAnswer: {
					letter: 'C',
					text: 'C. Comprehensive',
				},
			},
			{
				questionText: 'What does uninsured motorist coverage protect against?',
				options: {
					A: 'A. Weather damage',
					B: 'B. Mechanical failure',
					C: 'C. Drivers without insurance',
					D: 'D. Your deductible',
				},
				correctAnswer: {
					letter: 'C',
					text: 'C. Drivers without insurance',
				},
			},
			{
				questionText: 'Which coverage helps pay medical bills regardless of fault?',
				options: {
					A: 'A. Liability',
					B: 'B. Medical Payments / PIP',
					C: 'C. Collision',
					D: 'D. Gap',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Medical Payments / PIP',
				},
			},
		],
	},
	{
		moduleTitle: 'Topic 7: Liability Insurance',
		questions: [
			{
				questionText: 'What does bodily injury liability cover?',
				options: {
					A: 'A. Your injuries',
					B: 'B. Injuries to others',
					C: 'C. Vehicle repairs',
					D: 'D. Theft',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Injuries to others',
				},
			},
			{
				questionText: 'Property damage liability covers damage to what?',
				options: {
					A: 'A. Your car',
					B: 'B. Your home',
					C: 'C. Other people’s property',
					D: 'D. Medical bills',
				},
				correctAnswer: {
					letter: 'C',
					text: 'C. Other people’s property',
				},
			},
			{
				questionText: 'Who does liability insurance protect?',
				options: {
					A: 'A. Passengers',
					B: 'B. Other drivers',
					C: 'C. You as the driver',
					D: 'D. Mechanics',
				},
				correctAnswer: {
					letter: 'C',
					text: 'C. You as the driver',
				},
			},
			{
				questionText: 'Is liability insurance required by law in most states?',
				options: {
					A: 'A. Yes',
					B: 'B. No',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. Yes',
				},
			},
			{
				questionText: 'Liability insurance pays for your own car repairs.',
				options: {
					A: 'A. True',
					B: 'B. False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. False',
				},
			},
		],
	},
	{
		moduleTitle: 'Topic 8: Collision Coverage',
		questions: [
			{
				questionText: 'Collision coverage applies when you hit what?',
				options: {
					A: 'A. Another vehicle or object',
					B: 'B. A medical bill',
					C: 'C. Theft',
					D: 'D. Weather',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. Another vehicle or object',
				},
			},
			{
				questionText: 'Does collision cover hit-and-run accidents?',
				options: {
					A: 'A. Yes',
					B: 'B. No',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. Yes',
				},
			},
			{
				questionText: 'Is collision coverage required by law?',
				options: {
					A: 'A. Yes',
					B: 'B. No',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. No',
				},
			},
			{
				questionText: 'Who usually requires collision coverage?',
				options: {
					A: 'A. State government',
					B: 'B. Lenders/leasing companies',
					C: 'C. Police',
					D: 'D. Mechanics',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Lenders/leasing companies',
				},
			},
			{
				questionText: 'Collision coverage includes a deductible.',
				options: {
					A: 'A. True',
					B: 'B. False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. True',
				},
			},
		],
	},
	{
		moduleTitle: 'Topic 9: Comprehensive Coverage',
		questions: [
			{
				questionText: 'What type of damage does comprehensive cover?',
				options: {
					A: 'A. Accidents only',
					B: 'B. Non-collision events',
					C: 'C. Medical bills',
					D: 'D. Traffic tickets',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Non-collision events',
				},
			},
			{
				questionText: 'Which is covered by comprehensive insurance?',
				options: {
					A: 'A. Car accident',
					B: 'B. Theft',
					C: 'C. Speeding ticket',
					D: 'D. Oil change',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Theft',
				},
			},
			{
				questionText: 'Does comprehensive cover natural disasters?',
				options: {
					A: 'A. Yes',
					B: 'B. No',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. Yes',
				},
			},
			{
				questionText: 'Comprehensive insurance requires a deductible.',
				options: {
					A: 'A. True',
					B: 'B. False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. True',
				},
			},
			{
				questionText: 'Is comprehensive mandatory in all states?',
				options: {
					A: 'A. Yes',
					B: 'B. No',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. No',
				},
			},
		],
	},
	{
		moduleTitle: 'Topic 10: Deductibles',
		questions: [
			{
				questionText: 'What is a deductible?',
				options: {
					A: 'A. Monthly bill',
					B: 'B. Amount you pay before insurance',
					C: 'C. Coverage limit',
					D: 'D. Refund',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Amount you pay before insurance',
				},
			},
			{
				questionText: 'A higher deductible usually means what?',
				options: {
					A: 'A. Higher premium',
					B: 'B. Lower premium',
					C: 'C. No coverage',
					D: 'D. Free repairs',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Lower premium',
				},
			},
			{
				questionText: 'When do you pay a deductible?',
				options: {
					A: 'A. Every month',
					B: 'B. At renewal',
					C: 'C. When filing a claim',
					D: 'D. When buying a car',
				},
				correctAnswer: {
					letter: 'C',
					text: 'C. When filing a claim',
				},
			},
			{
				questionText: 'Deductibles apply to liability coverage.',
				options: {
					A: 'A. True',
					B: 'B. False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. False',
				},
			},
			{
				questionText: 'Choosing a deductible affects premium cost.',
				options: {
					A: 'A. True',
					B: 'B. False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. True',
				},
			},
		],
	},
	{
		moduleTitle: 'Topic 11: Premiums',
		questions: [
			{
				questionText: 'What is an insurance premium?',
				options: {
					A: 'A. Claim payout',
					B: 'B. Monthly or annual cost',
					C: 'C. Deductible',
					D: 'D. Discount',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Monthly or annual cost',
				},
			},
			{
				questionText: 'Which factor affects premium cost?',
				options: {
					A: 'A. Driving record',
					B: 'B. Eye color',
					C: 'C. Shoe size',
					D: 'D. Favorite food',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. Driving record',
				},
			},
			{
				questionText: 'Safer drivers usually pay what?',
				options: {
					A: 'A. Higher premiums',
					B: 'B. Lower premiums',
					C: 'C. No premiums',
					D: 'D. Same premiums',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Lower premiums',
				},
			},
			{
				questionText: 'Premiums are paid to whom?',
				options: {
					A: 'A. Police',
					B: 'B. Insurance company',
					C: 'C. DMV',
					D: 'D. Repair shop',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Insurance company',
				},
			},
			{
				questionText: 'Premiums can be paid monthly or annually.',
				options: {
					A: 'A. True',
					B: 'B. False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. True',
				},
			},
		],
	},
	{
		moduleTitle: 'Topic 12: Insurance Claims',
		questions: [
			{
				questionText: 'What is an insurance claim?',
				options: {
					A: 'A. Policy document',
					B: 'B. Request for payment',
					C: 'C. Traffic citation',
					D: 'D. Bill',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Request for payment',
				},
			},
			{
				questionText: 'When should you file a claim?',
				options: {
					A: 'A. After an accident',
					B: 'B. Before driving',
					C: 'C. Every month',
					D: 'D. At renewal',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. After an accident',
				},
			},
			{
				questionText: 'Who investigates a claim?',
				options: {
					A: 'A. Judge',
					B: 'B. Insurance adjuster',
					C: 'C. Police officer',
					D: 'D. Mechanic',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Insurance adjuster',
				},
			},
			{
				questionText: 'Claims can affect future premiums.',
				options: {
					A: 'A. True',
					B: 'B. False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. True',
				},
			},
			{
				questionText: 'False claims are legal.',
				options: {
					A: 'A. True',
					B: 'B. False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. False',
				},
			},
		],
	},
	{
		moduleTitle: 'Topic 13: Insurance Policy',
		questions: [
			{
				questionText: 'What is an insurance policy?',
				options: {
					A: 'A. Receipt',
					B: 'B. Legal contract',
					C: 'C. Claim form',
					D: 'D. License',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Legal contract',
				},
			},
			{
				questionText: 'What does a policy outline?',
				options: {
					A: 'A. Coverage and limits',
					B: 'B. Driving routes',
					C: 'C. Gas prices',
					D: 'D. Repair shops',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. Coverage and limits',
				},
			},
			{
				questionText: 'Policies include coverage limits.',
				options: {
					A: 'A. True',
					B: 'B. False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. True',
				},
			},
			{
				questionText: 'Policies can be canceled for nonpayment.',
				options: {
					A: 'A. True',
					B: 'B. False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. True',
				},
			},
			{
				questionText: 'Policy terms are negotiable after signing.',
				options: {
					A: 'A. True',
					B: 'B. False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. False',
				},
			},
		],
	},
	{
		moduleTitle: 'Topic 14: Coverage Limits',
		questions: [
			{
				questionText: 'What is a coverage limit?',
				options: {
					A: 'A. Minimum premium',
					B: 'B. Maximum payout',
					C: 'C. Deductible',
					D: 'D. Discount',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Maximum payout',
				},
			},
			{
				questionText: 'What happens if damages exceed limits?',
				options: {
					A: 'A. Insurance pays all',
					B: 'B. You pay the rest',
					C: 'C. Claim denied',
					D: 'D. No effect',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. You pay the rest',
				},
			},
			{
				questionText: 'Higher limits usually mean what?',
				options: {
					A: 'A. Lower cost',
					B: 'B. Higher premium',
					C: 'C. No coverage',
					D: 'D. Same price',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Higher premium',
				},
			},
			{
				questionText: 'Coverage limits apply to liability insurance.',
				options: {
					A: 'A. True',
					B: 'B. False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. True',
				},
			},
			{
				questionText: 'Limits protect against large financial loss.',
				options: {
					A: 'A. True',
					B: 'B. False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. True',
				},
			},
		],
	},
	{
		moduleTitle: 'Topic 15: Discounts',
		questions: [
			{
				questionText: 'Which can qualify you for a discount?',
				options: {
					A: 'A. Safe driving',
					B: 'B. Speeding tickets',
					C: 'C. Late payments',
					D: 'D. Claims',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. Safe driving',
				},
			},
			{
				questionText: 'Bundling policies can reduce premiums.',
				options: {
					A: 'A. True',
					B: 'B. False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. True',
				},
			},
			{
				questionText: 'Student discounts are based on what?',
				options: {
					A: 'A. GPA',
					B: 'B. Age',
					C: 'C. Income',
					D: 'D. Vehicle size',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. GPA',
				},
			},
			{
				questionText: 'Discounts are automatic.',
				options: {
					A: 'A. True',
					B: 'B. False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. False',
				},
			},
			{
				questionText: 'Anti-theft devices may reduce premiums.',
				options: {
					A: 'A. True',
					B: 'B. False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. True',
				},
			},
		],
	},
	{
		moduleTitle: 'Topic 16: Driving Record Impact',
		questions: [
			{
				questionText: 'What affects your insurance rate most?',
				options: {
					A: 'A. Driving history',
					B: 'B. Music taste',
					C: 'C. Phone brand',
					D: 'D. Weather',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. Driving history',
				},
			},
			{
				questionText: 'Accidents can cause premiums to do what?',
				options: {
					A: 'A. Decrease',
					B: 'B. Increase',
					C: 'C. Disappear',
					D: 'D. Stay the same',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Increase',
				},
			},
			{
				questionText: 'Tickets remain on record for several years.',
				options: {
					A: 'A. True',
					B: 'B. False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. True',
				},
			},
			{
				questionText: 'A clean record leads to lower premiums.',
				options: {
					A: 'A. True',
					B: 'B. False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. True',
				},
			},
			{
				questionText: 'Insurance companies ignore driving history.',
				options: {
					A: 'A. True',
					B: 'B. False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. False',
				},
			},
		],
	},
	{
		moduleTitle: 'Topic 17: Filing a Claim After an Accident',
		questions: [
			{
				questionText: 'What is the first thing you should do after an accident?',
				options: {
					A: 'A. Leave the scene',
					B: 'B. Ensure safety and call for help',
					C: 'C. Call your insurance immediately',
					D: 'D. Fix the car',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Ensure safety and call for help',
				},
			},
			{
				questionText: 'When should you contact your insurance company?',
				options: {
					A: 'A. Weeks later',
					B: 'B. Immediately or soon after',
					C: 'C. Only if forced',
					D: 'D. Never',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Immediately or soon after',
				},
			},
			{
				questionText: 'What information is helpful when filing a claim?',
				options: {
					A: 'A. Photos and police report',
					B: 'B. Social media posts',
					C: 'C. Opinions',
					D: 'D. Repair estimates only',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. Photos and police report',
				},
			},
			{
				questionText: 'Fault must be admitted at the scene.',
				options: {
					A: 'A. True',
					B: 'B. False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. False',
				},
			},
			{
				questionText: 'Claims should be reported honestly.',
				options: {
					A: 'A. True',
					B: 'B. False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. True',
				},
			},
		],
	},
	{
		moduleTitle: 'Topic 18: Insurance Adjusters',
		questions: [
			{
				questionText: 'What is an insurance adjuster?',
				options: {
					A: 'A. Lawyer',
					B: 'B. Investigator of claims',
					C: 'C. Mechanic',
					D: 'D. Agent',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Investigator of claims',
				},
			},
			{
				questionText: 'What does an adjuster determine?',
				options: {
					A: 'A. Fault and payout',
					B: 'B. Ticket fines',
					C: 'C. Vehicle price',
					D: 'D. Insurance laws',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. Fault and payout',
				},
			},
			{
				questionText: 'Adjusters work for whom?',
				options: {
					A: 'A. DMV',
					B: 'B. Insurance company',
					C: 'C. Police',
					D: 'D. Court',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Insurance company',
				},
			},
			{
				questionText: 'Adjusters inspect vehicle damage.',
				options: {
					A: 'A. True',
					B: 'B. False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. True',
				},
			},
			{
				questionText: 'Adjusters decide insurance premiums.',
				options: {
					A: 'A. True',
					B: 'B. False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. False',
				},
			},
		],
	},
	{
		moduleTitle: 'Topic 19: Rental Car Coverage',
		questions: [
			{
				questionText: 'What does rental car coverage provide?',
				options: {
					A: 'A. Gas',
					B: 'B. Temporary vehicle',
					C: 'C. Repairs',
					D: 'D. Insurance discount',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Temporary vehicle',
				},
			},
			{
				questionText: 'When is rental coverage used?',
				options: {
					A: 'A. After an accident',
					B: 'B. During oil changes',
					C: 'C. When selling a car',
					D: 'D. When renewing policy',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. After an accident',
				},
			},
			{
				questionText: 'Is rental coverage mandatory?',
				options: {
					A: 'A. Yes',
					B: 'B. No',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. No',
				},
			},
			{
				questionText: 'Rental coverage has daily limits.',
				options: {
					A: 'A. True',
					B: 'B. False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. True',
				},
			},
			{
				questionText: 'Rental coverage replaces collision insurance.',
				options: {
					A: 'A. True',
					B: 'B. False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. False',
				},
			},
		],
	},
	{
		moduleTitle: 'Topic 20: Medical Payments / PIP',
		questions: [
			{
				questionText: 'What does Medical Payments coverage pay for?',
				options: {
					A: 'A. Car repairs',
					B: 'B. Medical expenses',
					C: 'C. Property damage',
					D: 'D. Tickets',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Medical expenses',
				},
			},
			{
				questionText: 'PIP stands for what?',
				options: {
					A: 'A. Personal Injury Protection',
					B: 'B. Payment Insurance Plan',
					C: 'C. Premium Increase Program',
					D: 'D. Property Insurance Policy',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. Personal Injury Protection',
				},
			},
			{
				questionText: 'Does PIP cover passengers?',
				options: {
					A: 'A. Yes',
					B: 'B. No',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. Yes',
				},
			},
			{
				questionText: 'PIP applies regardless of fault.',
				options: {
					A: 'A. True',
					B: 'B. False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. True',
				},
			},
			{
				questionText: 'PIP is required in some states.',
				options: {
					A: 'A. True',
					B: 'B. False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. True',
				},
			},
		],
	},
	{
		moduleTitle: 'Topic 21: Uninsured / Underinsured Motorist Coverage',
		questions: [
			{
				questionText: 'What does uninsured motorist coverage protect against?',
				options: {
					A: 'A. Theft',
					B: 'B. Drivers without insurance',
					C: 'C. Weather damage',
					D: 'D. Repairs',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Drivers without insurance',
				},
			},
			{
				questionText: 'Underinsured motorist coverage applies when?',
				options: {
					A: 'A. Other driver has no insurance',
					B: 'B. Other driver lacks enough coverage',
					C: 'C. You are uninsured',
					D: 'D. You are at fault',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Other driver lacks enough coverage',
				},
			},
			{
				questionText: 'This coverage protects you and passengers.',
				options: {
					A: 'A. True',
					B: 'B. False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. True',
				},
			},
			{
				questionText: 'It covers vehicle damage and injuries.',
				options: {
					A: 'A. True',
					B: 'B. False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. True',
				},
			},
			{
				questionText: 'This coverage is required in all states.',
				options: {
					A: 'A. True',
					B: 'B. False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. False',
				},
			},
		],
	},
	{
		moduleTitle: 'Topic 22: Gap Insurance',
		questions: [
			{
				questionText: 'What is gap insurance?',
				options: {
					A: 'A. Covers repair gaps',
					B: 'B. Pays difference between loan and value',
					C: 'C. Covers rental cars',
					D: 'D. Covers tickets',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Pays difference between loan and value',
				},
			},
			{
				questionText: 'Who benefits most from gap insurance?',
				options: {
					A: 'A. Owners of older cars',
					B: 'B. Leased or financed vehicle owners',
					C: 'C. Pedestrians',
					D: 'D. Mechanics',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Leased or financed vehicle owners',
				},
			},
			{
				questionText: 'When is gap insurance useful?',
				options: {
					A: 'A. Theft or total loss',
					B: 'B. Oil change',
					C: 'C. Flat tire',
					D: 'D. Maintenance',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. Theft or total loss',
				},
			},
			{
				questionText: 'Gap insurance is mandatory.',
				options: {
					A: 'A. True',
					B: 'B. False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. False',
				},
			},
			{
				questionText: 'Gap insurance pays your deductible.',
				options: {
					A: 'A. True',
					B: 'B. False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. False',
				},
			},
		],
	},
	{
		moduleTitle: 'Topic 23: Policy Renewal and Cancellation',
		questions: [
			{
				questionText: 'What is policy renewal?',
				options: {
					A: 'A. Ending coverage',
					B: 'B. Continuing coverage',
					C: 'C. Filing a claim',
					D: 'D. Buying a car',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Continuing coverage',
				},
			},
			{
				questionText: 'Policies usually renew how often?',
				options: {
					A: 'A. Monthly',
					B: 'B. Every 6 or 12 months',
					C: 'C. Daily',
					D: 'D. Never',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Every 6 or 12 months',
				},
			},
			{
				questionText: 'Nonpayment can result in what?',
				options: {
					A: 'A. Discount',
					B: 'B. Cancellation',
					C: 'C. Refund',
					D: 'D. Bonus',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Cancellation',
				},
			},
			{
				questionText: 'Insurers must notify before cancellation.',
				options: {
					A: 'A. True',
					B: 'B. False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. True',
				},
			},
			{
				questionText: 'You can change insurers at renewal.',
				options: {
					A: 'A. True',
					B: 'B. False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. True',
				},
			},
		],
	},
	{
		moduleTitle: 'Topic 24: State Insurance Requirements',
		questions: [
			{
				questionText: 'Who sets minimum insurance requirements?',
				options: {
					A: 'A. Federal government',
					B: 'B. State government',
					C: 'C. Insurance companies',
					D: 'D. Police',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. State government',
				},
			},
			{
				questionText: 'Most states require what coverage?',
				options: {
					A: 'A. Collision',
					B: 'B. Liability',
					C: 'C. Comprehensive',
					D: 'D. Gap',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Liability',
				},
			},
			{
				questionText: 'Driving uninsured can lead to what?',
				options: {
					A: 'A. Discounts',
					B: 'B. Fines or license suspension',
					C: 'C. Free insurance',
					D: 'D. Lower premiums',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Fines or license suspension',
				},
			},
			{
				questionText: 'Requirements vary by state.',
				options: {
					A: 'A. True',
					B: 'B. False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. True',
				},
			},
			{
				questionText: 'Insurance laws never change.',
				options: {
					A: 'A. True',
					B: 'B. False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. False',
				},
			},
		],
	},
	{
		moduleTitle: 'Topic 25: Factors Affecting Insurance Rates',
		questions: [
			{
				questionText: 'What affects insurance rates?',
				options: {
					A: 'A. Driving record',
					B: 'B. Location',
					C: 'C. Vehicle type',
					D: 'D. All of the above',
				},
				correctAnswer: {
					letter: 'D',
					text: 'D. All of the above',
				},
			},
			{
				questionText: 'Younger drivers usually pay what?',
				options: {
					A: 'A. Less',
					B: 'B. More',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. More',
				},
			},
			{
				questionText: 'Sports cars usually cost more to insure.',
				options: {
					A: 'A. True',
					B: 'B. False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. True',
				},
			},
			{
				questionText: 'Credit history can affect rates in some states.',
				options: {
					A: 'A. True',
					B: 'B. False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. True',
				},
			},
			{
				questionText: 'Rates are the same for everyone.',
				options: {
					A: 'A. True',
					B: 'B. False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. False',
				},
			},
		],
	},
	{
		moduleTitle: 'Topic 26: Avoiding Insurance Fraud',
		questions: [
			{
				questionText: 'What is insurance fraud?',
				options: {
					A: 'A. Honest mistake',
					B: 'B. Lying for benefits',
					C: 'C. Filing claims',
					D: 'D. Paying premiums',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Lying for benefits',
				},
			},
			{
				questionText: 'Which is an example of fraud?',
				options: {
					A: 'A. Reporting a real accident',
					B: 'B. Exaggerating damages',
					C: 'C. Paying deductible',
					D: 'D. Buying insurance',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Exaggerating damages',
				},
			},
			{
				questionText: 'Fraud can lead to legal penalties.',
				options: {
					A: 'A. True',
					B: 'B. False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. True',
				},
			},
			{
				questionText: 'Fraud affects premiums for everyone.',
				options: {
					A: 'A. True',
					B: 'B. False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. True',
				},
			},
			{
				questionText: 'Fraud is harmless.',
				options: {
					A: 'A. True',
					B: 'B. False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. False',
				},
			},
		],
	},
	{
		moduleTitle: 'Topic 27: Responsible Driving and Insurance',
		questions: [
			{
				questionText: 'Responsible driving helps do what?',
				options: {
					A: 'A. Increase premiums',
					B: 'B. Lower insurance costs',
					C: 'C. Cancel policies',
					D: 'D. Avoid coverage',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Lower insurance costs',
				},
			},
			{
				questionText: 'Defensive driving courses can provide what?',
				options: {
					A: 'A. Tickets',
					B: 'B. Discounts',
					C: 'C. Fines',
					D: 'D. Claims',
				},
				correctAnswer: {
					letter: 'B',
					text: 'B. Discounts',
				},
			},
			{
				questionText: 'Following traffic laws reduces accidents.',
				options: {
					A: 'A. True',
					B: 'B. False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. True',
				},
			},
			{
				questionText: 'Safe drivers are considered lower risk.',
				options: {
					A: 'A. True',
					B: 'B. False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. True',
				},
			},
			{
				questionText: 'Insurance encourages responsible driving.',
				options: {
					A: 'A. True',
					B: 'B. False',
					C: '',
					D: '',
				},
				correctAnswer: {
					letter: 'A',
					text: 'A. True',
				},
			},
		],
	},
];

const QUIZ_MODULES = quizData.map((module, index) => ({
	...module,
	order: index + 1,
}));

function getModuleByOrder(moduleOrder) {
	const order = Number(moduleOrder);
	return QUIZ_MODULES.find((module) => module.order === order) || null;
}

function getChoiceLetter(choiceText) {
	const match = String(choiceText || '').trim().match(/^([A-D])\./);
	return match ? match[1] : '';
}

function buildQuestionsForModule(module) {
	if (!module) return [];
	return module.questions.map((question, idx) => {
		const options = question?.options || {};
		const optionEntries = Object.entries(options).filter(([, value]) => Boolean(value));
		const choices = optionEntries.map(([, value]) => value);
		const isTrueFalse = ['True', 'False'].includes(String(question?.correctAnswer?.letter || ''));
		return {
			id: `local_m${module.order}_${idx + 1}`,
			moduleOrder: module.order,
			moduleTitle: module.moduleTitle,
			type: isTrueFalse ? 'true_false' : 'multiple_choice',
			prompt: question.questionText,
			answerBank: options,
			choices,
			correctAnswer: question.correctAnswer,
			weight: isTrueFalse ? 0.5 : 1.0,
			localOnly: true,
		};
	});
}

function gradeAnswer(current, selected) {
	const expected = String(current?.correctAnswer?.letter ?? '').trim();
	const selectedText = String(selected ?? '').trim();
	if (!expected || !selectedText) return false;
	if (current?.type === 'true_false') {
		return expected.toLowerCase() === selectedText.toLowerCase();
	}
	const expectedLetter = expected.toUpperCase();
	const selectedLetter = getChoiceLetter(selectedText) || selectedText.toUpperCase();
	if (/^[A-D]$/.test(expectedLetter)) {
		return expectedLetter === selectedLetter;
	}
	return expectedLetter === selectedLetter;
}

function normalizeQuestion(q) {
	const type = String(q?.type || 'multiple_choice');
	const choices = Array.isArray(q?.choices) ? q.choices : [];
	return {
		id: String(q?.id || ''),
		type,
		prompt: String(q?.prompt || ''),
		choices,
		answerBank: q?.answerBank,
		moduleOrder: q?.moduleOrder ?? null,
		moduleTitle: String(q?.moduleTitle || q?.topic || ''),
		correctAnswer: q?.correctAnswer,
		weight: q?.weight,
		localOnly: Boolean(q?.localOnly),
	};
}

export default function KnowledgeQuizPage() {
	const [searchParams] = useSearchParams();
	const navigate = useNavigate();

	const customerIdParam = searchParams.get('customerId') || '';
	const moduleOrderParam = searchParams.get('moduleOrder') || '';

	const [customerId, setCustomerId] = useState(customerIdParam);
	const [moduleOrder, setModuleOrder] = useState(
		moduleOrderParam || String(QUIZ_MODULES[0]?.order ?? '')
	);
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState('');
	const [notice, setNotice] = useState('');
	const [curriculum] = useState(() =>
		QUIZ_MODULES.map((module) => ({
			order: module.order,
			module: `Topic ${module.order}: ${module.moduleTitle}`,
		}))
	);
	const [questions, setQuestions] = useState([]);
	const [idx, setIdx] = useState(0);
	const [selected, setSelected] = useState('');
	const [graded, setGraded] = useState(null);
	const [score, setScore] = useState({ earned: 0, possible: 0, correct: 0, total: 0 });
	const [isFinished, setIsFinished] = useState(false);

	const current = useMemo(() => (questions[idx] ? normalizeQuestion(questions[idx]) : null), [questions, idx]);

	const canStart = useMemo(() => !busy, [busy]);

	async function startQuiz() {
		setBusy(true);
		setError('');
		setNotice('');
		setGraded(null);
		setSelected('');
		setIdx(0);
		setScore({ earned: 0, possible: 0, correct: 0, total: 0 });
		setIsFinished(false);
		try {
			let effectiveModuleOrder = moduleOrder;
			if (!effectiveModuleOrder && curriculum.length && curriculum[0]?.order != null) {
				effectiveModuleOrder = String(curriculum[0].order);
				setModuleOrder(effectiveModuleOrder);
			}
			const module = getModuleByOrder(effectiveModuleOrder) || QUIZ_MODULES[0];
			const prepared = buildQuestionsForModule(module);
			setQuestions(prepared);
			if (!prepared.length) {
				setNotice('No quiz questions available yet for this module.');
			}
		} catch (e) {
			setQuestions([]);
			setError(e?.message || String(e));
		} finally {
			setBusy(false);
		}
	}

	function OptionRow({ value, text }) {
		const disabled = busy || graded != null;
		const isSelected = selected === String(value);
		return (
			<button
				type='button'
				disabled={disabled}
				onClick={() => setSelected(String(value))}
				style={{
					width: '100%',
					display: 'block',
					textAlign: 'left',
					padding: '10px 12px',
					borderRadius: 8,
					border: isSelected ? '2px solid #4da3ff' : '1px solid #333',
					background: isSelected ? '#001b2b' : '#0b0b0f',
					color: '#fff',
					cursor: disabled ? 'not-allowed' : 'pointer',
					fontSize: 15,
					lineHeight: 1.4,
				}}
			>
				<span>{text}</span>
			</button>
		);
	}

	async function submitAnswer() {
		setBusy(true);
		setError('');
		setNotice('');
		try {
			if (!current?.id) throw new Error('No current question.');
			if (!selected) throw new Error('Please pick an answer.');
			const isCorrect = gradeAnswer(current, selected);
			const weight = Number(
				current.weight ?? (current.type === 'true_false' || current.type === 'true/false' ? 0.5 : 1.0)
			);
			setGraded({
				correct: isCorrect,
				score: isCorrect ? weight : 0,
				weight,
			});
			setScore((s) => ({
				earned: s.earned + (isCorrect ? weight : 0),
				possible: s.possible + weight,
				correct: s.correct + (isCorrect ? 1 : 0),
				total: s.total + 1,
			}));
		} catch (e) {
			setError(e?.message || String(e));
		} finally {
			setBusy(false);
		}
	}

	function nextQuestion() {
		setGraded(null);
		setSelected('');
		setNotice('');
		if (idx + 1 >= questions.length) {
			setNotice('You finished the quiz!');
			setIsFinished(true);
			return;
		}
		setIdx((i) => i + 1);
	}

	async function retryQuiz() {
		await startQuiz();
	}

	const progressText = useMemo(() => {
		if (!questions.length) return '';
		return `Question ${idx + 1} of ${questions.length}`;
	}, [questions.length, idx]);

	const teacherBackUrl = useMemo(() => {
		const id = Number(customerId || customerIdParam);
		return Number.isFinite(id) && id > 0 ? `/teacher?customerId=${id}` : '/teacher';
	}, [customerId, customerIdParam]);

	const resourcesUrl = useMemo(() => {
		const id = Number(customerId || customerIdParam);
		if (!Number.isFinite(id) || id <= 0) return '/resources?from=quiz';
			const topicText = String(
				curriculum.find((m) => String(m?.order ?? '') === String(moduleOrder))?.module ||
				'auto insurance basics'
			);
		return `/resources?customerId=${id}&topic=${encodeURIComponent(topicText)}&from=quiz`;
	}, [customerId, customerIdParam, curriculum, moduleOrder]);

	return (
		<div style={{ padding: 24, maxWidth: 1000, margin: '0 auto' }}>
			<div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
				<h1 style={{ margin: 0 }}>Knowledge Check Quiz</h1>
				<Link to='/' style={{ color: '#ffffff', textDecoration: 'underline' }}>
					Back to Onboarding
				</Link>
			</div>

			<div style={{ marginTop: 16, display: 'flex', flexWrap: 'wrap', alignItems: 'end', gap: 12 }}>
				<div>
					<label style={{ display: 'block', marginBottom: 6 }}>Customer id</label>
					<input value={customerId} onChange={(e) => setCustomerId(e.target.value)} style={{ width: 240, padding: 10 }} placeholder='e.g. 46' />
				</div>
				<div>
					<label style={{ display: 'block', marginBottom: 6 }}>Module</label>
					<select
						value={moduleOrder}
						onChange={(e) => setModuleOrder(e.target.value)}
						disabled={busy || !curriculum.length}
						style={{ width: 420, maxWidth: '100%', padding: 10 }}
					>
						{curriculum.map((m) => (
							<option key={String(m?.order ?? m?.module)} value={String(m?.order ?? '')}>
								{m?.module}
							</option>
						))}
					</select>
				</div>
				<button onClick={startQuiz} disabled={!canStart} style={{ fontSize: '16px', padding: '10px 44px' }}>
					{busy ? 'Starting…' : 'Start quiz'}
				</button>
			</div>

			{error ? (
				<div style={{ marginTop: 16, background: '#2b0000', border: '1px solid #660000', padding: 12 }}>
					<strong>Problem:</strong> {error}
				</div>
			) : null}

			{questions.length ? (
				<div style={{ marginTop: 20 }}>
					<div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 12, flexWrap: 'wrap' }}>
						<h2 style={{ margin: 0 }}>{progressText}</h2>
						<div style={{ opacity: 0.9 }}>
							Score: {score.earned.toFixed(1)} / {score.possible.toFixed(1)} ({score.correct}/{score.total} correct)
						</div>
					</div>

					{isFinished ? (
						<div style={{ marginTop: 12, background: '#0b0b0f', border: '1px solid #222', padding: 14, borderRadius: 8 }}>
							<h2 style={{ marginTop: 0 }}>Quiz complete</h2>
							<div style={{ marginTop: 8, opacity: 0.95, lineHeight: 1.6 }}>
								<div>
									Final score: <strong>{score.earned.toFixed(1)}</strong> / <strong>{score.possible.toFixed(1)}</strong>
								</div>
								<div>
									Correct: <strong>{score.correct}</strong> out of <strong>{score.total}</strong>
								</div>
							</div>

							<div style={{ marginTop: 14, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
								<button onClick={retryQuiz} disabled={busy} style={{ fontSize: '16px', padding: '10px 30px' }}>
									{busy ? 'Restarting…' : 'Retry same quiz'}
								</button>
								<button onClick={() => navigate(resourcesUrl)} disabled={busy} style={{ fontSize: '16px', padding: '10px 18px' }}>
									Get learning resources
								</button>
								<button onClick={() => navigate(teacherBackUrl)} disabled={busy} style={{ fontSize: '16px', padding: '10px 18px' }}>
									Back to Teacher
								</button>
							</div>
						</div>
					) : current ? (
						<div style={{ marginTop: 12, background: '#0b0b0f', border: '1px solid #222', padding: 14, borderRadius: 8 }}>
							<div style={{ marginTop: 8, fontSize: 18, fontWeight: 600 }}>{current.prompt}</div>

							<div style={{ marginTop: 12 }}>
								<ul style={{ margin: 0, paddingLeft: 0, listStyle: 'none' }}>
									{current.choices.map((c, i) => (
										<li key={i} style={{ marginTop: 10, paddingLeft: 0 }}>
											<OptionRow value={String(c)} text={String(c)} />
										</li>
									))}
								</ul>
							</div>

							<div style={{ marginTop: 14, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
								<button onClick={submitAnswer} disabled={busy || graded != null} style={{ fontSize: '16px', padding: '10px 30px' }}>
									{busy ? 'Submitting…' : 'Submit'}
								</button>
								<button onClick={nextQuestion} disabled={busy || graded == null} style={{ fontSize: '16px', padding: '10px 30px' }}>
									Next
								</button>
								<button
									onClick={() => navigate(teacherBackUrl)}
									disabled={busy}
									style={{ fontSize: '16px', padding: '10px 18px' }}
								>
									Back to Teacher
								</button>
							</div>

							{selected ? (
								<div style={{ marginTop: 10, opacity: 0.85, fontSize: 13 }}>
									Selected: <span style={{ fontFamily: 'monospace' }}>{selected}</span>
								</div>
							) : null}

							{graded ? (
									<div style={{ marginTop: 14, padding: 12, border: '1px solid #333', borderRadius: 8, background: graded.correct ? '#001b2b' : '#2b0000' }}>
										<div>
											<strong>{graded.correct ? 'Correct' : 'Not quite'}</strong>
										</div>
									</div>
							) : null}
						</div>
					) : null}
				</div>
			) : null}
		</div>
	);
}
