import {
  Button,
  DialogActionTrigger,
  DialogTitle,
  Flex,
  Grid,
  GridItem,
  HStack,
  Icon,
  Input,
  Text,
  VStack,
} from "@chakra-ui/react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { Controller, type SubmitHandler, useForm } from "react-hook-form"
import {
  FiCheck,
  FiKey,
  FiLock,
  FiMail,
  FiPlus,
  FiShield,
  FiToggleRight,
  FiType,
  FiUserPlus,
} from "react-icons/fi"
import { type UserCreate, UsersService } from "@/client"
import type { ApiError } from "@/client/core/ApiError"
import FieldGuide, { type FieldGuideItem } from "@/components/Common/FieldGuide"
import useCustomToast from "@/hooks/useCustomToast"
import { emailPattern, handleError } from "@/utils"
import { Checkbox } from "../ui/checkbox"
import {
  DialogBody,
  DialogCloseTrigger,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogRoot,
  DialogTrigger,
} from "../ui/dialog"
import { Field } from "../ui/field"

interface UserCreateForm extends UserCreate {
  confirm_password: string
}

const fieldGuideItems: FieldGuideItem[] = [
  {
    icon: FiMail,
    label: "Email",
    description:
      "The user's email address. Used as the login identifier for the web management interface (not for TACACS+ device authentication).",
    example: "admin@example.com",
    required: true,
  },
  {
    icon: FiType,
    label: "Full Name",
    description:
      "The user's display name. Shown in the UI and audit logs for identification purposes.",
    example: "John Doe",
  },
  {
    icon: FiLock,
    label: "Password",
    description:
      "The login password for the web interface. Must meet the complexity requirements shown below the field (12+ chars, mixed case, numbers, special chars).",
    required: true,
  },
  {
    icon: FiShield,
    label: "Is Superuser",
    description:
      "Superusers have full administrative access to all features, including user management, system settings, and TACACS+ config generation.",
  },
  {
    icon: FiToggleRight,
    label: "Is Active",
    description:
      "Only active users can log in to the web interface. Deactivating a user prevents access without deleting their account.",
  },
  {
    icon: FiKey,
    label: "Disable Password Login",
    description:
      "When enabled, the user cannot log in with a password and must use an alternative method (OAuth, Passkey). Useful for enforcing SSO-only access.",
  },
]

const AddUser = () => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()
  const {
    control,
    register,
    handleSubmit,
    reset,
    watch,
    getValues,
    formState: { errors, isValid, isSubmitting },
  } = useForm<UserCreateForm>({
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      email: "",
      full_name: "",
      password: "",
      confirm_password: "",
      is_superuser: false,
      is_active: false,
      password_login_disabled: false,
    },
  })

  const password = watch("password", "")
  const passwordPolicies = [
    {
      text: "At least 12 characters",
      regex: /^.{12,}$/,
    },
    {
      text: "One lowercase letter (a-z)",
      regex: /[a-z]/,
    },
    {
      text: "One uppercase letter (A-Z)",
      regex: /[A-Z]/,
    },
    {
      text: "One number (0-9)",
      regex: /[0-9]/,
    },
    {
      text: "One special character (e.g. !@#$%)",
      regex: /[!"#$%&'()*+,-./:;<=>?@[\\\]^_`{|}~]/,
    },
  ]

  const mutation = useMutation({
    mutationFn: (data: UserCreate) =>
      UsersService.createUser({ requestBody: data }),
    onSuccess: () => {
      showSuccessToast("User created successfully.")
      reset()
      setIsOpen(false)
    },
    onError: (err: ApiError) => {
      handleError(err)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] })
    },
  })

  const onSubmit: SubmitHandler<UserCreateForm> = (data) => {
    mutation.mutate(data)
  }

  return (
    <DialogRoot
      size="xl"
      placement="center"
      open={isOpen}
      onOpenChange={({ open }) => setIsOpen(open)}
    >
      <DialogTrigger asChild>
        <Button value="add-user" my={4}>
          <FiPlus fontSize="16px" />
          Add User
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>Add User</DialogTitle>
          </DialogHeader>
          <DialogBody>
            <Grid templateColumns={{ base: "1fr", lg: "7fr 5fr" }} gap={6}>
              <GridItem>
                <Text mb={4} color="fg.muted" fontSize="sm">
                  Create a new web management user. This account is for the admin
                  interface — not for TACACS+ device authentication.
                </Text>
                <VStack gap={4}>
                  <Field
                    required
                    invalid={!!errors.email}
                    errorText={errors.email?.message}
                    label="Email"
                  >
                    <Input
                      {...register("email", {
                        required: "Email is required",
                        pattern: emailPattern,
                      })}
                      placeholder="Email"
                      type="email"
                    />
                  </Field>

                  <Field
                    invalid={!!errors.full_name}
                    errorText={errors.full_name?.message}
                    label="Full Name"
                  >
                    <Input
                      {...register("full_name")}
                      placeholder="Full name"
                      type="text"
                    />
                  </Field>

                  <Field
                    required
                    invalid={!!errors.password}
                    errorText={errors.password?.message}
                    label="Set Password"
                  >
                    <Input
                      {...register("password", {
                        required: "Password is required",
                        minLength: {
                          value: 12,
                          message: "Password must be at least 12 characters long",
                        },
                        validate: {
                          hasLower: (value) =>
                            /[a-z]/.test(value) ||
                            "Must contain one lowercase letter",
                          hasUpper: (value) =>
                            /[A-Z]/.test(value) ||
                            "Must contain one uppercase letter",
                          hasNumber: (value) =>
                            /[0-9]/.test(value) || "Must contain one number",
                          hasSpecial: (value) =>
                            /[!"#$%&'()*+,-./:;<=>?@[\\\]^_`{|}~]/.test(value) ||
                            "Must contain one special character",
                        },
                      })}
                      placeholder="Password"
                      type="password"
                    />
                  </Field>
                  <Field
                    required
                    invalid={!!errors.confirm_password}
                    errorText={errors.confirm_password?.message}
                    label="Confirm Password"
                  >
                    <Input
                      {...register("confirm_password", {
                        required: "Please confirm your password",
                        validate: (value) =>
                          value === getValues().password ||
                          "The passwords do not match",
                      })}
                      placeholder="Password"
                      type="password"
                    />
                  </Field>
                  <VStack align="start" w="full" color="gray.500" fontSize="sm">
                    <Text>Password must contain at least:</Text>
                    {passwordPolicies.map((policy, index) => {
                      const isMet = policy.regex.test(password)
                      return (
                        <HStack
                          key={index}
                          color={isMet ? "green.500" : "gray.500"}
                        >
                          <Icon as={FiCheck} />
                          <Text as="span" fontSize="sm">
                            {policy.text}
                          </Text>
                        </HStack>
                      )
                    })}
                  </VStack>
                </VStack>
                <Flex mt={4} direction="column" gap={4}>
                  <Controller
                    control={control}
                    name="is_superuser"
                    render={({ field }) => (
                      <Field disabled={field.disabled} colorPalette="teal">
                        <Checkbox
                          checked={field.value}
                          onCheckedChange={({ checked }) => field.onChange(checked)}
                        >
                          Is superuser?
                        </Checkbox>
                      </Field>
                    )}
                  />
                  <Controller
                    control={control}
                    name="is_active"
                    render={({ field }) => (
                      <Field disabled={field.disabled} colorPalette="teal">
                        <Checkbox
                          checked={field.value}
                          onCheckedChange={({ checked }) => field.onChange(checked)}
                        >
                          Is active?
                        </Checkbox>
                      </Field>
                    )}
                  />
                  <Controller
                    control={control}
                    name="password_login_disabled"
                    render={({ field }) => (
                      <Field disabled={field.disabled} colorPalette="teal">
                        <Checkbox
                          checked={field.value ?? false}
                          onCheckedChange={({ checked }) => field.onChange(checked)}
                        >
                          Disable password login?
                        </Checkbox>
                      </Field>
                    )}
                  />
                </Flex>
              </GridItem>

              <GridItem>
                <FieldGuide
                  items={fieldGuideItems}
                  icon={FiUserPlus}
                  subtitle="Learn what each field means for web management user accounts."
                  howItWorks="Web users are separate from TACACS+ users. These accounts control access to the admin interface where you manage TACACS+ configurations, view logs, and monitor the system."
                />
              </GridItem>
            </Grid>
          </DialogBody>

          <DialogFooter gap={2}>
            <DialogActionTrigger asChild>
              <Button
                variant="subtle"
                colorPalette="gray"
                disabled={isSubmitting}
              >
                Cancel
              </Button>
            </DialogActionTrigger>
            <Button
              variant="solid"
              type="submit"
              disabled={!isValid}
              loading={isSubmitting}
            >
              Save
            </Button>
          </DialogFooter>
        </form>
        <DialogCloseTrigger />
      </DialogContent>
    </DialogRoot>
  )
}

export default AddUser
