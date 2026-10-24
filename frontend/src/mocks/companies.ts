// src/mocks/companies.ts
import type { CompanyProfile, RoleItem, DemoProfileItem } from '../types/api';

export const MOCK_ROLES: RoleItem[] = [
  { code: 'ceo', name: 'Генеральный директор' },
  { code: 'cfo', name: 'Финансовый директор' },
  { code: 'accountant', name: 'Главный бухгалтер' },
];

export const MOCK_DEMO_PROFILES: DemoProfileItem[] = [
  {
    company_id: 'U_84920',
    company_name: 'УралМетЭкспорт',
    role: 'ceo',
    role_name: 'Генеральный директор',
  },
  {
    company_id: 'U_31044',
    company_name: 'АгроЛогистик',
    role: 'ceo',
    role_name: 'Генеральный директор',
  },
  {
    company_id: 'U_55912',
    company_name: 'ТехноСтрой',
    role: 'ceo',
    role_name: 'Генеральный директор',
  },
];

export const MOCK_COMPANIES: CompanyProfile[] = [
  {
    id: 'U_84920',
    company_name: 'УралМетЭкспорт',
    industry: {
      code: '24.10',
      name: 'Металлургия',
    },
    region: 'Свердловская обл.',
    city: 'г. Екатеринбург',
    age_range: '16-25',
    employees_range: 'более 250',
    business_stage: 'Зрелость',
    client_type: 'CLIENT',
    revenue: {
      value: 45_000_000_000,
      unit: 'RUB',
    },
    foreign_trade: {
      has_data: true,
      countries: ['Китай', 'Казахстан', 'Турция'],
    },
    bank_products: {
      rko: false,
      guarantee: false,
      loan: true,
      leasing: false,
      deposit: false,
      payroll: false,
      factoring: false,
    },
    group_id: 'group_84920_ural',
    organization_type: 'ЮЛ',
    ownership_form: 'Частная собственность',
    key_owner_flag: null,
    employees_spark_range: '251-500',
  },
  {
    id: 'U_31044',
    company_name: 'АгроЛогистик',
    industry: {
      code: '49.41',
      name: 'Логистика и ритейл',
    },
    region: 'Московская обл.',
    city: 'г. Химки',
    age_range: '6-15',
    employees_range: '101-250',
    business_stage: 'Рост',
    client_type: 'CLIENT',
    revenue: {
      value: 18_000_000_000,
      unit: 'RUB',
    },
    foreign_trade: {
      has_data: false,
      countries: [],
    },
    bank_products: {
      rko: false,
      guarantee: false,
      loan: false,
      leasing: true,
      deposit: false,
      payroll: false,
      factoring: true,
    },
    group_id: null,
    organization_type: 'ЮЛ',
    ownership_form: 'Частная собственность',
    key_owner_flag: null,
    employees_spark_range: '101-250',
  },
  {
    id: 'U_55912',
    company_name: 'ТехноСтрой',
    industry: {
      code: '41.20',
      name: 'Строительство',
    },
    region: 'г. Москва',
    city: 'г. Москва',
    age_range: '6-15',
    employees_range: '101-250',
    business_stage: 'Зрелость',
    client_type: 'CLIENT',
    revenue: {
      value: 25_000_000_000,
      unit: 'RUB',
    },
    foreign_trade: {
      has_data: false,
      countries: [],
    },
    bank_products: {
      rko: true,
      guarantee: true,
      loan: false,
      leasing: false,
      deposit: false,
      payroll: false,
      factoring: false,
    },
    group_id: 'group_55912_stroy',
    organization_type: 'ЮЛ',
    ownership_form: 'Частная собственность',
    key_owner_flag: null,
    employees_spark_range: null,
  },
  {
    id: 'U_67',
    company_name: 'Компания U_67',
    industry: {
      code: '46.51',
      name: 'Торговля оптовая компьютерами',
    },
    region: 'Новосибирская область',
    city: 'г. Новосибирск',
    age_range: '16-25',
    employees_range: 'Менее 15',
    business_stage: 'Рождение',
    client_type: 'PROSPECT',
    revenue: {
      value: 136493.0,
      unit: 'unconfirmed',
    },
    foreign_trade: {
      has_data: false,
      countries: [],
    },
    bank_products: {
      rko: false,
      guarantee: false,
      loan: false,
      leasing: false,
      deposit: false,
      payroll: false,
      factoring: false,
    },
    group_id: 'group_134463_sb',
    organization_type: null,
    ownership_form: null,
    key_owner_flag: null,
    employees_spark_range: null,
  },
  {
    id: 'U_101',
    company_name: 'Компания U_101',
    industry: {
      code: '46.51',
      name: 'Оптовая торговля',
    },
    region: 'г. Москва',
    city: 'г. Москва',
    age_range: '6-15',
    employees_range: '15-50',
    business_stage: 'Рост',
    client_type: 'CLIENT',
    revenue: {
      value: 4_200_000_000,
      unit: 'RUB',
    },
    foreign_trade: {
      has_data: true,
      countries: ['Беларусь'],
    },
    bank_products: {
      rko: true,
      guarantee: false,
      loan: true,
      leasing: false,
      deposit: true,
      payroll: true,
      factoring: false,
    },
    group_id: 'group_134463_sb',
    organization_type: 'ЮЛ',
    ownership_form: 'Частная собственность',
    key_owner_flag: null,
    employees_spark_range: null,
  },
  {
    id: 'U_202',
    company_name: 'УралСтальПром (U_202)',
    industry: {
      code: '24.10',
      name: 'Производство стали',
    },
    region: 'Свердловская область',
    city: 'г. Нижний Тагил',
    age_range: 'более 25',
    employees_range: 'более 250',
    business_stage: 'Зрелость',
    client_type: 'CLIENT',
    revenue: {
      value: 12_500_000_000,
      unit: 'RUB',
    },
    foreign_trade: {
      has_data: false,
      countries: [],
    },
    bank_products: {
      rko: true,
      guarantee: true,
      loan: true,
      leasing: true,
      deposit: false,
      payroll: false,
      factoring: false,
    },
    group_id: null,
    organization_type: 'ЮЛ',
    ownership_form: 'Частная собственность',
    key_owner_flag: null,
    employees_spark_range: null,
  },
];

export function formatRevenue(revenue: CompanyProfile['revenue']): string {
  const { value, unit } = revenue;
  if (unit === 'unconfirmed') return `${value.toLocaleString('ru-RU')} (единица не подтверждена)`;
  if (unit !== 'RUB') return `${value.toLocaleString('ru-RU')} ${unit}`;
  if (value >= 1_000_000_000) {
    const billions = +(value / 1_000_000_000).toFixed(1);
    return `${billions} млрд ₽`;
  }
  if (value >= 1_000_000) {
    const millions = +(value / 1_000_000).toFixed(1);
    return `${millions} млн ₽`;
  }
  return `${value.toLocaleString('ru-RU')} ₽`;
}

export function formatCompanyProducts(company: CompanyProfile): string {
  const active: string[] = [];
  const bp = company.bank_products;

  if (bp.loan) active.push('Кредиты');
  if (bp.leasing) active.push('Лизинг');
  if (bp.factoring) active.push('Факторинг');
  if (bp.guarantee) active.push('Гарантии');
  if (bp.rko) active.push('РКО');
  if (bp.deposit) active.push('Депозиты');
  if (bp.payroll) active.push('Зарплатный проект');
  if (company.foreign_trade?.has_data) active.push('ВЭД');

  return active.length > 0 ? active.join(', ') : 'Нет подтверждённых продуктов';
}
